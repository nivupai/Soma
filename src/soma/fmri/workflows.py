"""Reproducible first-level workflows with private artifacts and immutable reports."""

import hashlib
import json
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import yaml
from nilearn.masking import compute_epi_mask

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import sha256, write_json
from soma.experiments.cache import canonical_id
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import Estimate, contrast, fit
from soma.fmri.ingestion import select_run
from soma.fmri.outputs import export_estimate
from soma.fmri.plots import figures
from soma.fmri.records import FunctionalRun
from soma.fmri.spatial import SpatialMap, roi_estimates
from soma.imaging.nifti import save_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.cache import source_hash
from soma.pipeline.derivatives import private_output


def configuration(path: Path) -> ModelConfig:
    values = yaml.safe_load(path.read_text())
    values["confound_columns"] = tuple(values.get("confound_columns", []))
    return ModelConfig(**values)


def freeze_check() -> None:
    for path in ["configs/fmri-freeze.json", "configs/fmri-spm-amendment.json"]:
        seal = json.loads(Path(path).read_text())
        for name, expected in seal["files_sha256"].items():
            if sha256(Path(name)) != expected:
                raise ValueError("Frozen fMRI protocol/config mismatch")


def analyze(
    run: FunctionalRun,
    config: ModelConfig,
    definition: Contrast,
    output: Path,
    *,
    allow_unvalidated_demo: bool = False,
    truth: dict[str, Any] | None = None,
    resume: bool = False,
    input_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    private_output(output)
    identity = canonical_id(
        {
            "run": run.identity,
            "input": run.provenance,
            "data": __import__("hashlib")
            .sha256(np.asanyarray(run.image.dataobj).tobytes())
            .hexdigest(),
            "mask": hashlib.sha256(run.mask.array().tobytes()).hexdigest(),
            "geometry": run.mask.geometry(),
            "events": run.events.to_dict("list"),
            "confounds_csv_sha256": hashlib.sha256(
                run.confounds.to_csv(index=False, float_format="%.17g").encode()
            ).hexdigest(),
            "config": asdict(config),
            "contrast": asdict(definition),
            "source": source_hash(),
            "nilearn": version("nilearn"),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "allow_unvalidated_demo": allow_unvalidated_demo,
        }
    )
    if output.exists():
        if not resume:
            raise FileExistsError("Report exists; choose new output or explicit identical resume")
        prior = json.loads((output / "summary.json").read_text())
        if prior["run_identity"] != identity:
            raise ValueError("Stale cached report: data/config/source identity changed")
        manifest = json.loads((output / "manifest.json").read_text())
        for relative, expected in manifest["outputs_sha256"].items():
            if sha256(output / relative) != expected:
                raise ValueError("Corrupt cached output; never silently reuse")
        return {**prior, "verified_output_reuse": True}
    report = AnatomyReport(output, asdict(config), run.provenance, seed=13042)
    with report.stage("design_and_glm"):
        fitted = fit(run, config, allow_unvalidated_demo=allow_unvalidated_demo)
    with report.stage("contrasts"):
        estimate = contrast(fitted, definition)
    with report.stage("ROI"):
        effect = Volume(np.asarray(estimate.maps["effect_size"].dataobj), run.mask.affine_m)
        rows = roi_estimates(
            SpatialMap(effect, run.subject, run.space, "BOLD effect", {"source": "GLM"}),
            SpatialMap(
                run.mask,
                run.subject,
                run.space,
                "analysis foreground",
                {
                    "source": "prespecified analysis mask",
                    "label_mapping": {1: "whole analysis foreground"},
                },
            ),
        )
    with report.stage("publication_and_schema"):
        exported = export_estimate(estimate, output)
    fitted.design.to_csv(output / "design.tsv", sep="\t", index_label="time_s")
    write_json(output / "design-diagnostics.json", fitted.diagnostics)
    write_json(output / "roi.json", rows)
    with report.stage("figures"):
        figures(output, fitted, estimate, truth)
    if input_spec is not None:
        write_json(output / "input-spec.json", input_spec)
    result = report.finish(
        {
            "status": "complete",
            "run_identity": identity,
            "identity": run.identity,
            "source_tree_sha256": source_hash(),
            "nilearn": version("nilearn"),
            "preprocessing": run.preprocessing,
            "design": fitted.diagnostics,
            "contrast": estimate.metadata,
            "ROI": rows,
            "export": exported,
            "validated_preprocessing_claimed": run.preprocessing == "validated",
            "population_inference": False,
            "verified_output_reuse": False,
        }
    )
    return result


def spm_run(root: Path, preparation: Path) -> FunctionalRun:
    """No preprocessing system: an explicit raw educational source and EPI ROI heuristic."""
    preparation.mkdir(parents=True, exist_ok=False)
    image = next(root.glob("sub-*/func/*_bold.nii"))
    raw: Any = nib.load(image)
    start = time.perf_counter()
    epi = compute_epi_mask(raw)
    volume = Volume(
        np.asarray(epi.dataobj, dtype=np.uint8),
        epi.affine * np.array([0.001] * 3 + [1])[:, None],
        "labels",
    )
    path = preparation / "foreground-mask.nii.gz"
    save_nifti(volume, path)
    write_json(
        preparation / "inspection.json",
        {
            "shape": raw.shape,
            "zooms": [float(v) for v in raw.header.get_zooms()],
            "units": raw.header.get_xyzt_units(),
            "mask_wall_s": time.perf_counter() - start,
            "mask_method": "Nilearn compute_epi_mask ROI heuristic; brain extraction unvalidated",
            "input_sha256": sha256(image),
            "metadata": json.loads((root / "task-auditory_bold.json").read_text()),
        },
    )
    return select_run(root, subject="01", task="auditory", mask=path, exploratory_raw=True)


def load_spec(spec: dict[str, Any]) -> tuple[FunctionalRun, ModelConfig, Contrast, bool]:
    config = configuration(Path(spec.get("model_config", "configs/fmri-design.yaml")))
    from dataclasses import replace

    overrides = {
        k: spec[k]
        for k in ["smoothing_fwhm", "initial_spikes", "noise_model", "hrf_model"]
        if k in spec
    }
    config = replace(config, **overrides)
    if spec.get("dataset") == "spm-auditory":
        freeze_check()
        run = spm_run(Path(spec["data_root"]) / "spm_auditory/MoAEpilot", Path(spec["preparation"]))
    else:
        run = select_run(
            Path(spec["input"]),
            subject=str(spec["subject"]),
            task=spec["task"],
            session=spec.get("session"),
            run=spec.get("run"),
            space=spec.get("space"),
            derivatives=Path(spec["derivatives"]),
            preprocessing_evidence=spec.get("preprocessing_evidence"),
        )
    definition = Contrast(
        spec.get("contrast", "task"), spec.get("weights", {spec.get("contrast", "task"): 1.0})
    )
    return run, config, definition, bool(spec.get("allow_unvalidated_demo", False))


def fit_config(path: Path, output: Path, *, contrast_name: str | None = None) -> dict[str, Any]:
    spec = yaml.safe_load(path.read_text())
    if contrast_name is not None:
        spec["contrast"] = contrast_name
        spec.pop("weights", None)
    spec["preparation"] = str(output.parent / (output.name + "-input-preparation"))
    run, config, definition, allow = load_spec(spec)
    result = analyze(run, config, definition, output, allow_unvalidated_demo=allow, input_spec=spec)
    # The source specification is sealed in the report output manifest.
    return result


def estimate_spec(spec: dict[str, Any]) -> Estimate:
    run, cfg, definition, allow = load_spec(spec)
    return contrast(fit(run, cfg, allow_unvalidated_demo=allow), definition)
