"""Supplemental, explicitly post-hoc development-only fixed-CSP diagnostic."""

import argparse
import copy
import time
import warnings
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from threadpoolctl import threadpool_limits

from soma.core.provenance import manifest, sha256
from soma.decoding.config import digest, identity, read_protocol
from soma.decoding.data import load_trials
from soma.decoding.metrics import compare_models, subject_scores
from soma.decoding.models import make_pipeline, require_unfitted
from soma.decoding.splits import outer_splits, validate_split
from soma.simulations.calibration import atomic_json
from soma.statistics.inference import InferenceConfig, infer_mean


def run(root: Path, output: Path, specification: Path) -> dict[str, Any]:
    plan = yaml.safe_load(specification.read_text())
    if specification.with_suffix(".sha256").read_text().strip() != digest(plan):
        raise ValueError("Supplemental sensitivity seal mismatch")
    protocol, checksum = read_protocol(Path("configs/decoding.yaml"))
    if plan["initial_protocol_sha256"] != checksum or plan["heldout_accessed"]:
        raise ValueError("This diagnostic is development-only")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    datasets, configs, coverage = {}, {}, []
    for variant, update in plan["variants"].items():
        cfg = copy.deepcopy(protocol)
        cfg["preprocessing"].update(update)
        data, records = load_trials(root, tuple(plan["subjects"]), cfg)
        datasets[variant], configs[variant] = data, cfg
        coverage.extend({"variant": variant, **record} for record in records)
    common = set.intersection(*(set(d.metadata.trial_id) for d in datasets.values()))
    if not common:
        raise ValueError("No shared QC-retained observations")
    pd.DataFrame(coverage).to_csv(output / "record_coverage.csv", index=False)
    retention = []
    for variant, dataset in datasets.items():
        retained = np.flatnonzero(dataset.metadata.trial_id.isin(common))
        retention.append(
            {
                "variant": variant,
                "retained_before_intersection": len(dataset.y),
                "shared_trials": len(retained),
            }
        )
        datasets[variant] = dataset.subset(retained)
    pd.DataFrame(retention).to_csv(output / "retention.csv", index=False)
    predictions, failures, fits, partitions = [], [], [], {}
    for variant, dataset in datasets.items():
        cfg = configs[variant]
        for mode in ("within-subject", "cross-subject"):
            for fold in outer_splits(dataset, mode, cfg["outer_subject_folds"]):
                try:
                    membership = validate_split(dataset, fold)
                    partitions[membership["membership_sha256"]] = membership
                    estimator = make_pipeline("csp_lda", cfg, plan["fixed_parameters"])
                    require_unfitted(estimator)
                    tick = time.perf_counter()
                    with (
                        warnings.catch_warnings(record=True) as caught,
                        threadpool_limits(limits=1),
                    ):
                        warnings.simplefilter("always")
                        estimator.fit(dataset.X[fold.train], dataset.y[fold.train])
                        pred = estimator.predict(dataset.X[fold.test])
                        score = estimator.decision_function(dataset.X[fold.test])
                        probability = estimator.predict_proba(dataset.X[fold.test])[:, 1]
                    fits.append(
                        {
                            "variant": variant,
                            "mode": mode,
                            "fold": fold.name,
                            "partition": membership["membership_sha256"],
                            "seconds": time.perf_counter() - tick,
                            "warnings": [str(w.message) for w in caught],
                            "params": plan["fixed_parameters"],
                        }
                    )
                    for i, index in enumerate(fold.test):
                        row = dataset.metadata.iloc[index]
                        predictions.append(
                            {
                                "mode": mode,
                                "model": variant,
                                "subject": int(row.subject),
                                "run": int(row.run),
                                "trial_id": row.trial_id,
                                "label": int(dataset.y[index]),
                                "prediction": int(pred[i]),
                                "score": float(score[i]),
                                "probability": float(probability[i]),
                                "calibration_trials": 0,
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {"variant": variant, "mode": mode, "fold": fold.name, "error": str(exc)}
                    )
    predicted = pd.DataFrame(predictions)
    predicted.to_csv(output / "predictions.csv", index=False)
    rows, contrasts = [], []
    comparison_cfg = copy.deepcopy(protocol)
    comparison_cfg["primary_comparisons"] = [
        [v, "primary"] for v in plan["variants"] if v != "primary"
    ]
    for mode, frame in predicted.groupby("mode"):
        scores = subject_scores(frame)
        scores.assign(mode=mode).to_csv(output / f"metrics-{mode}.csv", index=False)
        paired, influence = compare_models(scores, comparison_cfg)
        contrasts.append(paired.assign(mode=mode))
        influence.to_csv(output / f"influence-{mode}.csv", index=False)
        for variant, values in scores.groupby("model"):
            subject = values.groupby("subject").balanced_accuracy.mean().to_numpy(float)
            row = infer_mean(subject, ("t",), InferenceConfig(seed=protocol["seed"]))[0]
            rows.append(
                {"mode": mode, "variant": variant, **row, "warnings": ";".join(row["warnings"])}
            )
    summary = pd.DataFrame(rows)
    summary.to_csv(output / "summary.csv", index=False)
    pd.concat(contrasts).to_csv(output / "comparisons.csv", index=False)
    atomic_json(output / "failures.json", failures)
    atomic_json(output / "fits.json", fits)
    atomic_json(output / "partitions.json", partitions)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for ax, (mode, group) in zip(axes, summary.groupby("mode"), strict=True):
        for i, row in enumerate(group.to_dict("records")):
            ax.scatter(i, row["estimate"], color="#3268a8")
            if row["ci_low"] is not None:
                ax.plot([i, i], [row["ci_low"], row["ci_high"]], color="#3268a8")
        ax.set(
            xticks=range(len(group)),
            xticklabels=group.variant,
            ylabel="Subject balanced accuracy",
            title=f"{mode}; fixed CSP; shared trials n={len(common)}",
        )
        ax.tick_params(axis="x", rotation=25)
        ax.axhline(0.5, color="black", linestyle="--", linewidth=0.6)
    fig.suptitle(
        "Post-hoc development diagnostic; subject t intervals; no held-out choice",
        fontsize=9,
    )
    fig.savefig(output / "preprocessing_sensitivity.png", dpi=160)
    plt.close(fig)
    atomic_json(
        output / "manifest.json",
        manifest(
            {
                "datasets": {name: data.fingerprint for name, data in datasets.items()},
                "script_sha256": sha256(Path(__file__)),
                "supplement_sha256": digest(plan),
            },
            {
                "initial_protocol_sha256": checksum,
                "software": identity(),
                "plan": plan,
                "primary_and_heldout_rules_changed": False,
            },
            {"output": str(output.resolve())},
            protocol["seed"],
        ),
    )
    return {
        "status": "complete" if not failures else "partial",
        "fits": len(fits),
        "failures": len(failures),
        "shared_trials": len(common),
        "wall_seconds": time.perf_counter() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--specification", type=Path, default=Path("configs/decoding-sensitivity.yaml")
    )
    args = parser.parse_args()
    print(run(args.data_dir, args.output, args.specification))
