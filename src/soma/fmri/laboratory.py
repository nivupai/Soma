"""Independent synthetic validation, sensitivity and null-model receipts."""

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import write_json
from soma.experiments.fmri_simulation import simulate
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import analytical_ols, contrast, fit
from soma.fmri.retest import retest
from soma.fmri.workflows import analyze
from soma.pipeline.derivatives import private_output
from soma.validation.plots import save


def laboratory(output: Path, seed: int = 13042) -> dict[str, Any]:
    private_output(output)
    report = AnatomyReport(
        output, {"seed": seed, "validation_seeds": list(range(13142, 13162))}, seed=seed
    )
    cfg = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    definition = Contrast("task", {"task": 1.0})
    with report.stage("simulation"):
        run, truth = simulate(seed)
    with report.stage("full_pipeline"):
        primary = analyze(run, cfg, definition, output / "primary", truth=truth)
    with report.stage("OLS_oracle"):
        fitted = fit(run, cfg)
        estimate = contrast(fitted, definition)
        locations = np.argwhere(truth["positive"])[:3]
        y = np.stack([run.image.get_fdata()[tuple(p)] for p in locations], axis=1)
        reference = analytical_ols(fitted.design.to_numpy(), y, definition.vector(fitted.design))
        effect = np.array([estimate.maps["effect_size"].get_fdata()[tuple(p)] for p in locations])
        variance = np.array(
            [estimate.maps["effect_variance"].get_fdata()[tuple(p)] for p in locations]
        )
        oracle = {
            "max_effect_error": float(np.max(abs(effect - reference["effect"]))),
            "max_variance_error": float(np.max(abs(variance - reference["variance"]))),
        }
        if oracle["max_effect_error"] > 1e-7 or oracle["max_variance_error"] > 1e-7:
            raise ValueError("Independent OLS oracle mismatch")
    with report.stage("sensitivity"):
        rows = []
        settings: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
            ("primary", {}, {}),
            ("no-confounds", {"confound_columns": ()}, {}),
            ("cosine-drift", {"drift_model": "cosine", "confound_columns": ("motion",)}, {}),
            ("HRF-derivative", {"hrf_model": "spm + derivative"}, {}),
            ("HRF-mismatch", {}, {"hrf_delay": 2.0}),
            ("AR-noise-OLS", {}, {"ar": 0.6}),
            ("AR-noise-AR1", {"noise_model": "ar1"}, {"ar": 0.6}),
            ("spatial-noise", {}, {"spatial_sigma": 0.7}),
            ("TR1", {}, {"tr": 1.0, "n_scans": 160}),
            ("smoothing", {"smoothing_fwhm": 3.0}, {}),
        ]
        for label, updates, simulation in settings:
            r, t = simulate(seed, **simulation)
            f = fit(r, replace(cfg, **updates))
            e = contrast(f, definition)
            values = np.asarray(e.maps["effect_size"].dataobj)
            rows.append(
                {
                    "setting": label,
                    "positive_mean_beta": float(values[t["positive"]].mean()),
                    "negative_mean_beta": float(values[t["negative"]].mean()),
                    "rejected_voxels": e.metadata["rejected_voxels"],
                    "lag1": f.diagnostics["mean_native_residual_lag1"],
                    "config": asdict(f.config),
                }
            )
    with report.stage("null_models"):
        null = []
        for seed_value in range(13142, 13162):
            for ar in [0.0, 0.6]:
                r, _ = simulate(seed_value, beta=0, ar=ar)
                for noise_model in ["ols"] if ar == 0 else ["ols", "ar1"]:
                    e = contrast(fit(r, replace(cfg, noise_model=noise_model)), definition)
                    mask = r.mask.array().astype(bool)
                    p = e.maps["p_two_sided"].get_fdata()[mask]
                    null.append(
                        {
                            "seed": seed_value,
                            "ar": ar,
                            "noise_model": noise_model,
                            "uncorrected_p05_fraction": float(np.mean(p < 0.05)),
                            "FDR_any_rejection": e.metadata["rejected_voxels"] > 0,
                        }
                    )
    with report.stage("synthetic_retest"):
        other, _ = simulate(seed + 1, session="retest")
        second = contrast(fit(other, cfg), definition)
        reliability = retest(estimate, second)
    with report.stage("plots"):
        fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
        labels = [r["setting"] for r in rows]
        axes[0].barh(labels, [r["positive_mean_beta"] for r in rows])
        axes[0].axvline(3, color="black")
        axes[0].set_title("Synthetic positive ROI mean beta (truth=3)")
        axes[1].barh(labels, [r["rejected_voxels"] for r in rows])
        axes[1].set_title("FDR rejection sensitivity")
        axes[2].bar(
            ["correlation", "activation Dice"],
            [reliability["map_correlation"], reliability["activation_Dice"]],
        )
        axes[2].set_title("Synthetic test/retest, not human reliability")
        save(
            output,
            "sensitivity-retest",
            fig,
            {
                "positive_mean_beta": [r["positive_mean_beta"] for r in rows],
                "negative_mean_beta": [r["negative_mean_beta"] for r in rows],
                "settings": np.array(labels),
                "retest_effect_first": estimate.maps["effect_size"].get_fdata(),
                "retest_effect_second": second.maps["effect_size"].get_fdata(),
            },
        )
    write_json(output / "sensitivity.json", rows)
    write_json(output / "null.json", null)
    summary_null = {}
    for ar, model in [(0.0, "ols"), (0.6, "ols"), (0.6, "ar1")]:
        entries = [r for r in null if r["ar"] == ar and r["noise_model"] == model]
        summary_null[f"AR{ar}-{model}"] = {
            "n": len(entries),
            "uncorrected_p05_fraction_mean": float(
                np.mean([r["uncorrected_p05_fraction"] for r in entries])
            ),
            "FDR_any_rejection_fraction": float(np.mean([r["FDR_any_rejection"] for r in entries])),
            "scope": "20 finite simulations, Monte Carlo uncertainty; not proof of calibrated FDR",
        }
    return report.finish(
        {
            "status": "complete",
            "primary": primary,
            "oracle": oracle,
            "null": summary_null,
            "sensitivity": rows,
            "synthetic_retest": reliability,
            "real_test_retest_available": False,
            "real_multimodal_completed": False,
        }
    )
