"""Frozen human-reference addendum using existing cohort, metric and report APIs."""

import hashlib
import json
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from soma.anatomy.reporting import AnatomyReport
from soma.benchmarks.segmentation import LabelVolume, intensity_baseline, score
from soma.core.provenance import sha256, write_json
from soma.datasets.external_anatomy import TISSUES
from soma.datasets.human_mri import (
    align_t1,
    discover_human,
    inventory_read,
    load_human,
    mapped_reference,
    safe_local_output,
    verify_inventory_inputs,
)
from soma.datasets.registry import REFERENCE_REGISTRY
from soma.imaging.nifti import save_nifti
from soma.imaging.volumes import Volume
from soma.validation.cohort import subject_interval


def human_configuration(path: Path) -> dict[str, Any]:
    seal = json.loads(Path("configs/human-tissues-freeze.json").read_text())
    for name, digest in seal["files_sha256"].items():
        if sha256(Path(name)) != digest:
            raise ValueError("Human addendum protocol/config seal mismatch")
    if path.resolve() != Path("configs/human-tissues.yaml").resolve():
        raise ValueError("Unsealed human study configuration")
    return dict(yaml.safe_load(path.read_text()))


def inventory_human(config: Path, output: Path) -> dict[str, Any]:
    cfg = human_configuration(config)
    safe_local_output(output)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    with report.stage("discovery_metadata_and_training_archive_checks"):
        inventory = discover_human(Path(cfg["ibsr_root"]), Path(cfg["mrbrains_root"]))
    write_json(output / "inventory.json", inventory)
    write_json(
        output / "inventory-freeze.json",
        {
            "inventory_sha256": sha256(output / "inventory.json"),
            "protocol_seal_sha256": sha256(Path("configs/human-tissues-freeze.json")),
            "evaluation_performed": False,
            "baseline_revision": "10ead8c",
        },
    )
    return report.finish(
        {
            "status": "inventory_complete",
            "counts": inventory["counts"],
            "failures": inventory["failures"],
            "test_payloads_read": False,
        }
    )


def predict_t1(image: Volume) -> LabelVolume:
    start = time.perf_counter()
    output = intensity_baseline(image)
    return LabelVolume(
        output,
        image.metadata["subject"],
        image.metadata["space"],
        TISSUES,
        {
            "tool": "Soma global multi-Otsu baseline",
            "version": version("soma-neuro"),
            "model_version": "none; fixed M10 parameters",
            "input_contrast": "T1",
            "input_sha256": image.metadata["source_sha256"],
            "truth_used": False,
            "options": output.metadata,
            "runtime_s": time.perf_counter() - start,
            "label_mapping": {0: 0, 1: 1, 2: 2, 3: 3},
            "aligned_input_array_sha256": hashlib.sha256(
                np.ascontiguousarray(image.array()).tobytes()
            ).hexdigest(),
            "transform_history": image.metadata.get("resampling"),
        },
    )


def evaluate_human_subject(record: dict[str, Any], output: Path) -> dict[str, Any]:
    dataset, subject = record["dataset"], record["subject"]
    if dataset not in REFERENCE_REGISTRY:
        raise ValueError("Dataset absent from Soma reference registry")
    safe_local_output(output)
    output.mkdir(parents=True, exist_ok=False)
    image = load_human(Path(record["image"]), dataset=dataset, subject=subject, role="intensity")
    native = load_human(Path(record["reference"]), dataset=dataset, subject=subject, role="labels")
    if image.metadata["source_sha256"] == native.metadata["source_sha256"]:
        raise ValueError("Reference cannot be independent prediction input")
    image, alignment = align_t1(image, native, dataset=dataset)
    # This function consumes only image intensities/geometry; references never fit thresholds.
    prediction = predict_t1(image)
    save_nifti(prediction.volume, output / "prediction.nii.gz")
    reference, valid = mapped_reference(native, dataset)
    if dataset == "mrbrains13":
        testing = load_human(
            Path(record["testing_style_reference"]), dataset=dataset, subject=subject, role="labels"
        )
        if not native.same_grid(testing) or not np.array_equal(reference.array(), testing.array()):
            raise ValueError("Native training/evaluation-style ontology consistency failed")
    if np.array_equal(prediction.volume.array(), reference.array()):
        raise ValueError("Reference-identical label result requires independent audit")
    reference_lv = LabelVolume(
        reference,
        subject,
        record["space"],
        TISSUES,
        {
            "path": record["reference"],
            "sha256": native.metadata["source_sha256"],
            "evidence_type": (
                "provided manually guided tissue reference; "
                "upstream preprocessing lineage shared for IBSR"
            ),
            "native_labels_preserved": True,
            "mapping": reference.metadata["mapping"],
            "annotation_error_free": False,
        },
    )
    metrics = score(prediction, reference_lv, valid_mask=valid if dataset == "mrbrains13" else None)
    save_nifti(valid, output / "valid-domain.nii.gz")
    metadata = {
        "image": image.metadata,
        "native_reference": native.metadata,
        "image_geometry": image.geometry(),
        "reference_geometry": native.geometry(),
        "alignment": alignment,
        "prediction": prediction.provenance,
        "prediction_sha256": sha256(output / "prediction.nii.gz"),
    }
    write_json(output / "geometry-provenance.json", metadata)
    write_json(output / "metrics.json", metrics)
    # Private native slice, full numeric companions; no reorientation by eye or fitted alignment.
    axis = 2
    index = image.shape[axis] // 2
    arrays = {
        "image_slice": np.take(image.array(), index, axis=axis),
        "reference_slice": np.take(reference.array(), index, axis=axis),
        "prediction_slice": np.take(prediction.volume.array(), index, axis=axis),
        "valid_slice": np.take(valid.array(), index, axis=axis),
        "slice_axis_index": np.array([axis, index]),
        "affine_m": image.affine_m,
    }
    np.savez_compressed(output / "overlay-arrays.npz", **arrays)
    from soma.validation.human_plots import overlay_plot

    overlay_plot(output, arrays, dataset)
    return {
        **metrics,
        "dataset": dataset,
        "partition": record["partition"],
        "resampled_intensity": alignment["resampled"],
        "prediction_wall_s": prediction.provenance["runtime_s"],
        "native_reference_codes": np.unique(native.array()).tolist(),
        "native_geometry": native.geometry(),
    }


def cohort_summary(rows: list[dict[str, Any]], *, seed: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dataset in ["ibsr-v2", "mrbrains13"]:
        selected = [r for r in rows if r["dataset"] == dataset]
        tissue: dict[str, Any] = {}
        for code, name in TISSUES.items():
            tissue[name] = {}
            for metric in [
                "Dice",
                "Jaccard",
                "ASSD_mm",
                "HD95_mm",
                "absolute_volume_error_mm3",
                "signed_volume_error_mm3",
                "signed_relative_volume_error",
            ]:
                values = [
                    t[metric]
                    for r in selected
                    for t in r["labels"]
                    if t["label"] == code and t[metric] is not None
                ]
                tissue[name][metric] = subject_interval(values, seed=seed) if values else None
        result[dataset] = {
            "subjects": len(selected),
            "macro_Dice": subject_interval([r["macro_Dice"] for r in selected], seed=seed)
            if selected
            else None,
            "tissues": tissue,
            "statistical_unit": "subject",
            "population_certification": False,
        }
    return result


def benchmark_human(
    config: Path, inventory_path: Path, output: Path, *, phase: str
) -> dict[str, Any]:
    cfg = human_configuration(config)
    safe_local_output(output)
    if phase not in ("development", "external"):
        raise ValueError("Explicit development or external phase required")
    freeze = json.loads(inventory_path.with_name("inventory-freeze.json").read_text())
    if (
        sha256(inventory_path) != freeze["inventory_sha256"]
        or sha256(Path("configs/human-tissues-freeze.json")) != freeze["protocol_seal_sha256"]
    ):
        raise ValueError("Input inventory/protocol binding mismatch")
    inventory = inventory_read(inventory_path)
    verify_inventory_inputs(inventory)
    selected = [r for r in inventory["subjects"] if r["partition"] == phase]
    report = AnatomyReport(
        output,
        {**cfg, "phase": phase, "inventory_sha256": sha256(inventory_path)},
        seed=cfg["seed"],
    )
    rows = []
    failures = []
    with report.stage("load_alignment_prediction_scoring_and_figures"):
        for i, record in enumerate(selected):
            start = time.perf_counter()
            try:
                row = evaluate_human_subject(record, output / f"case-{i + 1:03d}")
                row["wall_s"] = time.perf_counter() - start
                rows.append(row)
            except (ValueError, OSError) as exc:
                failures.append(
                    {"subject": record["subject"], "status": "FAIL", "reason": str(exc)}
                )
    summaries = cohort_summary(rows, seed=cfg["seed"])
    flat = [
        {"subject": r["subject"], "dataset": r["dataset"], "partition": r["partition"], **t}
        for r in rows
        for t in r["labels"]
    ]
    if flat:
        pd.DataFrame(flat).drop(columns=["boundaries"]).to_csv(
            output / "per-subject-tissue.csv", index=False
        )
    write_json(output / "subject-results.json", {"subjects": rows, "failures": failures})
    from soma.validation.human_plots import cohort_figures

    cohort_figures(output, rows)
    expected = 18 if phase == "development" else 5
    summary = {
        "status": "complete" if len(rows) == expected and not failures else "incomplete",
        "phase": phase,
        "requested": len(selected),
        "completed": len(rows),
        "expected_release_count": expected,
        "failures": failures,
        "failure_frequency": len(failures) / len(selected) if selected else None,
        "cohorts": summaries,
        "test_payloads_read": False,
        "skull_scalp_validation": False,
        "BEM_anatomical_readiness": "INDETERMINATE",
        "note": "Dataset-specific descriptive tissue evaluation, not hidden-test challenge scores",
    }
    return report.finish(summary)
