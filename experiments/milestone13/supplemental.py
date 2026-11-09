"""Component performance and explicit synthetic spatial/multimodal demonstrations."""

import resource
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TypeVar

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
from scipy.ndimage import gaussian_filter

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import write_json
from soma.fmri.design import Contrast, build_design, nuisance
from soma.fmri.glm import contrast, fit
from soma.fmri.ingestion import select_run
from soma.fmri.spatial import (
    SpatialMap,
    compare_regions,
    project_points,
    roi_estimates,
    sample_points,
)
from soma.fmri.workflows import configuration
from soma.geometry import Frame, Points
from soma.imaging.resampling import resample
from soma.imaging.volumes import Volume
from soma.pipeline.cache import source_hash
from soma.validation.plots import save

T = TypeVar("T")


def main() -> None:
    root = Path("reports/milestone13-supplemental")
    report = AnatomyReport(
        root,
        {"synthetic_spatial": True, "SPM_sensitivity": "prespecified exploratory alternatives"},
        seed=13042,
    )
    times = {}

    def timed(name: str, operation: Callable[[], T]) -> T:
        start = time.perf_counter()
        value = operation()
        times[name] = time.perf_counter() - start
        return value

    source = Path("data/external/spm-auditory/spm_auditory/MoAEpilot")
    image_path = next(source.glob("sub-*/func/*bold.nii"))

    def load() -> object:
        image = nib.load(image_path)
        np.asanyarray(image.dataobj)
        return image

    timed("functional_load_materialize_s", load)
    run = select_run(
        source,
        subject="01",
        task="auditory",
        mask=Path("reports/milestone13-spm-input-preparation/foreground-mask.nii.gz"),
        exploratory_raw=True,
    )
    cfg = replace(
        configuration(Path("configs/fmri-design.yaml")), initial_spikes=4, smoothing_fwhm=6.0
    )
    timed("confounds_s", lambda: nuisance(run, cfg))
    timed("design_s", lambda: build_design(run, cfg))
    fitted = timed("design_and_glm_s", lambda: fit(run, cfg, allow_unvalidated_demo=True))
    definition = Contrast("listening", {"listening": 1})
    estimate = timed("contrast_s", lambda: contrast(fitted, definition))
    effect = SpatialMap(
        Volume(estimate.maps["effect_size"].get_fdata(), run.mask.affine_m),
        run.subject,
        run.space,
        "BOLD effect",
        {"source": "exploratory GLM"},
    )
    roi = SpatialMap(
        run.mask,
        run.subject,
        run.space,
        "whole foreground",
        {"source": "intensity mask", "label_mapping": {1: "analysis foreground"}},
    )
    timed("ROI_s", lambda: roi_estimates(effect, roi))
    timed("same_grid_resampling_s", lambda: resample(effect.volume, effect.volume))
    real = []
    for name, updates in [
        ("primary", {}),
        ("OLS", {"noise_model": "ols"}),
        ("no-initial-spikes", {"initial_spikes": 0}),
        ("HRF-derivative", {"hrf_model": "spm + derivative"}),
        ("no-smoothing", {"smoothing_fwhm": 0.0}),
    ]:
        f = (
            fitted
            if name == "primary"
            else fit(run, replace(cfg, **updates), allow_unvalidated_demo=True)
        )
        e = contrast(f, definition)
        real.append(
            {
                "setting": name,
                "foreground_mean_beta": float(
                    e.maps["effect_size"].get_fdata()[run.mask.array().astype(bool)].mean()
                ),
                "rejected_voxels": e.metadata["rejected_voxels"],
                "native_residual_lag1": f.diagnostics["mean_native_residual_lag1"],
                "whitened_residual_lag1": f.diagnostics["mean_whitened_residual_lag1"],
            }
        )
    # Analytic spatial field: f(v)=i+2j+3k, exact trilinear interpolation oracle.
    indices = np.indices((7, 7, 7))
    field = indices[0] + 2 * indices[1] + 3 * indices[2]
    affine = np.diag([0.003, 0.003, 0.003, 1.0])
    affine[:3, 3] = -0.009
    image = SpatialMap(
        Volume(field, affine),
        "synthetic",
        "analytic",
        "linear field",
        {"source": "entirely synthetic"},
    )
    voxel = np.array([[1.5, 2.5, 3.5], [4.5, 3.5, 2.5]])
    points = Points(voxel * 0.003 - 0.009, Frame.RAS)
    recovered = sample_points(image, points, subject="synthetic", space="analytic")
    expected = voxel @ np.array([1.0, 2.0, 3.0])
    error = float(np.max(np.abs(recovered - expected)))
    if error > 1e-10:
        raise ValueError("Independent spatial interpolation oracle failed")
    projected, coverage = project_points(
        image, points, recovered, subject="synthetic", space="analytic"
    )
    np.savez_compressed(
        root / "spatial-oracle.npz",
        field=field,
        voxel=voxel,
        world_RAS_m=points.xyz,
        expected=expected,
        recovered=recovered,
        projection=projected.array(),
        coverage=coverage.array(),
    )
    region_names = ["anterior", "middle", "posterior"]
    fvalues = np.array([1.0, 3.0, 2.0])
    evalues = np.array([0.5, 2.0, 1.5])
    common = {
        "subject": "synthetic",
        "dataset": "synthetic-cohort",
        "release": "analytic-v1",
        "task": "simulation",
        "visit": "simulation",
        "roi_ontology": "synthetic-three-regions",
        "spatial_evidence": "analytic coordinate oracle",
    }
    left = {
        **common,
        "modality": "EEG",
        "quantity": "simulated source power",
        "values": dict(zip(region_names, evalues, strict=True)),
    }
    right = {
        **common,
        "modality": "fMRI",
        "quantity": "simulated BOLD effect",
        "values": dict(zip(region_names, fvalues, strict=True)),
    }
    comparison = compare_regions(left, right, mode="cross-dataset")
    blurred = gaussian_filter(field.astype(float), 1.0)
    registration_shift_error = float(np.mean(abs(field[1:] - field[:-1])))
    smooth_error = float(np.sqrt(np.mean((blurred - field) ** 2)))
    leakage = np.array([[0.8, 0.2, 0], [0.1, 0.8, 0.1], [0, 0.2, 0.8]]) @ evalues
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    x = np.arange(3)
    axes[0].bar(x - 0.15, evalues, 0.3, label="simulated EEG")
    axes[0].bar(x + 0.15, fvalues, 0.3, label="simulated BOLD")
    axes[0].set_xticks(x, region_names)
    axes[0].legend()
    axes[0].set_title("Descriptive simulated regions; different units")
    axes[1].barh([r["setting"] for r in real], [r["rejected_voxels"] for r in real])
    axes[1].set_title("Raw SPM exploratory sensitivity: FDR count")
    axes[2].scatter(expected, recovered)
    axes[2].set(xlabel="Analytic field oracle", ylabel="Trilinear sample")
    save(
        root,
        "spatial-multimodal-sensitivity",
        fig,
        {
            "simulated_EEG": evalues,
            "simulated_BOLD": fvalues,
            "leakage_example": leakage,
            "SPM_rejected_voxels": [r["rejected_voxels"] for r in real],
            "expected": expected,
            "recovered": recovered,
        },
    )
    write_json(root / "real-sensitivity.json", real)
    report.finish(
        {
            "status": "complete",
            "source_tree_sha256": source_hash(),
            "component_times_s": times,
            "image_shape": run.image.shape,
            "component_peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**2 if sys.platform == "darwin" else 1024),
            "spatial_oracle_max_error": error,
            "synthetic_registration_shift_3mm_field_error": registration_shift_error,
            "synthetic_smoothing_RMSE": smooth_error,
            "synthetic_source_leakage_example": leakage.tolist(),
            "multimodal": comparison,
            "real_multimodal_completed": False,
            "SPM_sensitivity": real,
            "motion_confounds_available": False,
            "retrospective_accuracy_tuning": False,
        }
    )


if __name__ == "__main__":
    main()
