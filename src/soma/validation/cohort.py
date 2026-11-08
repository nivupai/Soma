"""Subject-disjoint tissue scoring and backend interoperability with explicit failures."""

import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import label

from soma.anatomy.reporting import AnatomyReport
from soma.benchmarks.segmentation import LabelVolume, intensity_baseline, score
from soma.core.provenance import sha256, write_json
from soma.datasets.external_anatomy import TISSUES, local_reference_manifest
from soma.datasets.references import load_reference
from soma.imaging.volumes import Volume
from soma.validation.config import configuration


def validate_split(
    records: list[dict[str, Any]], development: list[str], holdout: list[str]
) -> None:
    if set(development) & set(holdout):
        raise ValueError("Development and holdout subjects overlap")
    ids = [r["subject"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate subject identity")
    seen_assets: dict[tuple[str, str], str] = {}
    for r in records:
        for field in ("image", "reference"):
            path = Path(r[field]) if field in r else None
            if path is not None and path.is_file():
                asset_key = (field, sha256(path))
                if asset_key in seen_assets and seen_assets[asset_key] != r["subject"]:
                    raise ValueError("Repeated source assets across subject identities/splits")
                seen_assets[asset_key] = r["subject"]
        if r["split"] not in ("development", "holdout"):
            raise ValueError("Explicit development/holdout split required")
        allowed = development if r["split"] == "development" else holdout
        if r["subject"] not in allowed:
            raise ValueError("Subject absent from frozen split or mislabeled split")
        for key in ("reference_subject", "image_subject", "prediction_subject"):
            if key in r and r[key] != r["subject"]:
                raise ValueError("Image/reference/prediction subject identity mismatch")


def backend_prediction(path: Path, record: dict[str, Any], reference: LabelVolume) -> LabelVolume:
    required = (
        "tool",
        "version",
        "model_version",
        "input_contrast",
        "label_mapping",
        "transform_history",
        "options",
        "runtime_s",
        "truth_used",
        "input_sha256",
    )
    if any(k not in record for k in required) or record["truth_used"] is not False:
        raise ValueError("Complete independent segmentation backend provenance required")
    if record["input_contrast"] != "T1" or record["runtime_s"] < 0:
        raise ValueError("Supported T1 backend and nonnegative runtime required")
    if (
        path.resolve() == Path(reference.provenance["path"]).resolve()
        or sha256(path) == reference.provenance["sha256"]
    ):
        raise ValueError("Reference cannot be its own prediction")
    if reference.provenance["sha256"] == record["input_sha256"]:
        raise ValueError("Prediction was produced from the reference labels")
    v = load_reference(path, kind="labels", subject=reference.subject, space=reference.space)
    mapping = {int(k): int(v) for k, v in record["label_mapping"].items()}
    if any(x not in (0, *TISSUES) for x in mapping.values()) or not set(
        np.unique(v.array())
    ).issubset(mapping):
        raise ValueError("Incomplete or incompatible native-label ontology mapping")
    values = np.zeros(v.shape, dtype=np.uint16)
    for source, target in mapping.items():
        values[v.array() == source] = target
    if v.same_grid(reference.volume) and np.array_equal(values, reference.volume.array()):
        raise ValueError("Reference-identical label content requires a separate independence audit")
    return LabelVolume(
        Volume(values, v.affine_m, "labels", v.metadata),
        reference.subject,
        reference.space,
        TISSUES,
        {**record, "path": str(path), "sha256": sha256(path)},
    )


def subject_interval(values: Any, *, seed: int = 11042, repetitions: int = 2000) -> dict[str, Any]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all() or repetitions < 100:
        raise ValueError("Finite independent subject statistics required")
    if len(x) < 2:
        return {
            "n_subjects": len(x),
            "mean": float(x.mean()),
            "CI95": None,
            "SD": None,
            "unit": "subject",
        }
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(repetitions, len(x)))].mean(axis=1)
    return {
        "n_subjects": len(x),
        "mean": float(x.mean()),
        "SD": float(x.std(ddof=1)),
        "CI95": np.quantile(means, [0.025, 0.975]).tolist(),
        "unit": "subject",
        "scope": "selected small cohort, not broad population certification",
    }


def evaluate_subject(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    subject, space = record["subject"], record["space"]
    for key in (
        "reference_provenance",
        "acquisition",
        "modality",
        "image",
        "reference",
        "reference_ontology",
    ):
        if key not in record:
            raise ValueError("Missing subject imaging/reference metadata: " + key)
    if (
        record["modality"] != "T1"
        or {int(k): v for k, v in record["reference_ontology"].items()} != TISSUES
    ):
        raise ValueError("Incompatible tissue ontology or imaging contrast")
    if not record["reference_provenance"].get("evidence_type"):
        raise ValueError("Reference annotation provenance required")
    imagepath, refpath = Path(record["image"]), Path(record["reference"])
    if imagepath.resolve() == refpath.resolve() or sha256(imagepath) == sha256(refpath):
        raise ValueError("Reference labels are not a valid independent MRI input")
    image = load_reference(imagepath, kind="intensity", subject=subject, space=space)
    ref = load_reference(refpath, kind="labels", subject=subject, space=space)
    if not set(np.unique(ref.array())).issubset({0, *TISSUES}):
        raise ValueError("Undeclared native reference labels; explicit ontology mapping required")
    if not image.same_grid(ref):
        raise ValueError("Native MRI/reference grids differ; no implicit registration/resampling")
    reference = LabelVolume(
        ref,
        subject,
        space,
        TISSUES,
        {**record["reference_provenance"], "path": str(refpath), "sha256": sha256(refpath)},
    )
    start = time.perf_counter()
    if record.get("prediction"):
        backend = record["backend"]
        if backend["input_sha256"] != sha256(imagepath):
            raise ValueError("Backend input does not match the declared subject MRI")
        prediction = backend_prediction(Path(record["prediction"]), backend, reference)
    else:
        prediction = LabelVolume(
            intensity_baseline(image),
            subject,
            space,
            TISSUES,
            {
                "tool": "Soma global multi-Otsu baseline",
                "version": "0.11.0",
                "model_version": "none",
                "input_sha256": sha256(imagepath),
                "truth_used": False,
                "input_contrast": "T1",
                "parameters": "M10 frozen 256-bin/2%foreground, no reference ROI",
            },
        )
    result = score(prediction, reference)
    result.update(
        {
            "split": record["split"],
            "acquisition": record["acquisition"],
            "backend_wall_s": time.perf_counter() - start,
            "components": {
                str(k): {
                    "reference": int(label(ref.array() == k)[1]),
                    "prediction": int(label(prediction.volume.array() == k)[1]),
                }
                for k in TISSUES
            },
        }
    )
    axis = 2
    index = image.shape[axis] // 2
    arrays = {
        "image_slice": np.take(image.array(), index, axis=axis),
        "reference_slice": np.take(ref.array(), index, axis=axis),
        "prediction_slice": np.take(prediction.volume.array(), index, axis=axis),
        "slice_axis_index": np.array([axis, index]),
    }
    return result, arrays


def cohort_benchmark(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    local = local_reference_manifest(Path(cfg["cohort_manifest"]))
    records = local["subjects"]
    validate_split(records, cfg["development_subjects"], cfg["holdout_subjects"])
    selected = [r for r in records if r["split"] == cfg["split"]]
    rows = []
    failures = []
    arrays = {}
    with report.stage("tissue_scoring"):
        for record in selected:
            try:
                row, a = evaluate_subject(record)
                rows.append(row)
                arrays.update({record["subject"] + "__" + k: v for k, v in a.items()})
            except (ValueError, OSError, KeyError) as exc:
                failures.append(
                    {"subject": record["subject"], "status": "FAIL", "diagnostic": str(exc)}
                )
    expected = (
        cfg["development_subjects"][:1]
        if cfg["split"] == "development"
        else cfg["holdout_subjects"]
    )
    missing = [s for s in expected if s not in [r["subject"] for r in selected]]
    summary = {
        "status": "complete"
        if rows and not failures and not missing
        else "incomplete_reference_evaluation",
        "split": cfg["split"],
        "subjects": rows,
        "failures": failures,
        "missing_subjects": missing,
        "requested_subjects": expected,
        "failure_frequency": len(failures) / len(selected) if selected else None,
        "access_diagnostic": local.get("diagnostic"),
        "inference_unit": "subject",
        "macro_Dice": subject_interval([r["macro_Dice"] for r in rows]) if rows else None,
        "subgroups": {},
        "population_generalization_claimed": False,
        "manifest_sha256": sha256(Path(cfg["cohort_manifest"]))
        if Path(cfg["cohort_manifest"]).exists()
        else None,
    }
    for field in ("scanner", "protocol"):
        groups = {str(r["acquisition"].get(field, "unknown")) for r in rows}
        summary["subgroups"][field] = {}
        for group in groups:
            vals = [
                r["macro_Dice"]
                for r in rows
                if str(r["acquisition"].get(field, "unknown")) == group
            ]
            summary["subgroups"][field][group] = (
                subject_interval(vals)
                if group != "unknown" and len(vals) >= 2
                else {"status": "unsupported", "n_subjects": len(vals)}
            )
    write_json(output / "subject-results.json", summary)
    if arrays:
        np.savez_compressed(output / "overlays.npz", **arrays)
    from soma.validation.plots import cohort_plots

    cohort_plots(output, summary, arrays)
    return report.finish(summary)
