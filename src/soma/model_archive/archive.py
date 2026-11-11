"""Immutable M17 release manifests around complete M23 numeric capsules."""

from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from soma.core.provenance import sha256
from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.eeg_benchmark.protocol import MODELS
from soma.external_eeg.contracts import compatibility, validate_contract
from soma.external_eeg.models import import_model, predict
from soma.human.permissions import PermissionEvidence, check_permission
from soma.model_archive.protocol import inspect_training
from soma.protocol.model import SealedProtocol
from soma.results.contracts import canonical, create_result
from soma.results.io import load_result, save_result
from soma.workflow.model import digest
from soma.workflow.privacy import redact_export


def numerical_receipt(
    values: dict[str, Any], arrays: dict[str, Any], output: Path, method: str
) -> None:
    envelope = create_result(
        "experiment.manifest",
        {
            "computation": method,
            "inputs": {},
            "environment": environment_snapshot(),
            "assumptions": ["source-only fit; integrity is not independent validation"],
            "validation": {"scope": "numeric archive"},
            "limitations": ["No human external evaluation"],
        },
        arrays=arrays,
        values=values,
        provenance={},
        method={"id": method, "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(envelope, arrays, output)


def safe_reference(root: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe archive storage reference")
    result = (root / p).resolve(strict=True)
    if not result.is_relative_to(root.resolve()) or result.is_symlink():
        raise ValueError("Escaped model reference")
    return result


def archive_root(path: Path) -> Path:
    if path.parent.name != "manifest" or path.name != "result.json":
        raise ValueError("Expected explicit manifest/result.json archive layout")
    return path.parent.parent


def inspect_archive(path: Path, expected_id: str) -> dict[str, Any]:
    e, arrays = load_result(path)
    if e["method"] != {"id": "soma.model-release", "version": "1"} or arrays:
        raise ValueError("Unsupported model release version")
    d = dict(e["payload"]["values"])
    if (
        d.get("id") != expected_id
        or digest({k: v for k, v in d.items() if k != "id"}) != expected_id
    ):
        raise ValueError("Model release identity mismatch")
    if (
        redact_export(d) != d
        or d["schema"] != "soma.model-release/1"
        or d["historical_m22"] is not False
    ):
        raise ValueError("Invalid model-release provenance or private path")
    v = inspect_training(SealedProtocol(canonical(d["protocol"])))
    if d["protocol_fingerprint"] != SealedProtocol(canonical(d["protocol"])).protocol.fingerprint:
        raise ValueError("Model/protocol mismatch")
    for key in ["source_fingerprint", "inventory_fingerprint"]:
        value = d.get(key, "")
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Missing source-data fingerprint")
    if set(d["models"]) != set(MODELS) or d["contract"] != v["contract"] or d["classes"] != [0, 1]:
        raise ValueError("Missing models or incompatible class/feature contract")
    if (
        d["inventory_fingerprint"]
        != SealedProtocol(canonical(d["protocol"])).protocol.document()["optional_metadata"][
            "inventory_fingerprint"
        ]
    ):
        raise ValueError("Inventory/protocol mismatch")
    for model, row in d["models"].items():
        capsule = safe_reference(archive_root(path), row["file"])
        if sha256(capsule) != row["sha256"]:
            raise ValueError("Changed capsule metadata")
        state, numeric = import_model(capsule, row["id"])
        training = state["training"]
        if (
            state["environment"] != d["environment"]
            or state["implementation"] != d["implementation"]
            or training["source_dataset"] != d["dataset"]
        ):
            raise ValueError("Capsule environment/implementation/dataset mismatch")
        if (
            state["model"] != model
            or state["contract"] != d["contract"]
            or training["protocol_fingerprint"] != d["protocol_fingerprint"]
            or training["source_fingerprint"] != d["source_fingerprint"]
            or training["parameters"] != v["parameters"][model]
        ):
            raise ValueError("Capsule/model/training binding mismatch")
        origin = (
            "SYNTHETIC_SOURCE_FIT"
            if v["dataset"] == "synthetic-external-v1"
            else "EEGBCI_PROSPECTIVE_SOURCE_FIT"
        )
        if training["origin"] != origin or any(
            a.dtype != np.dtype("float64") for a in numeric.values()
        ):
            raise ValueError("Unsupported origin or numerical precision")
    return d


def authorize(
    d: dict[str, Any], permission: PermissionEvidence | None, notice: bytes | None
) -> None:
    if d["dataset"] == "synthetic-external-v1":
        return
    if permission is None or notice is None:
        raise ValueError("Human model prediction requires current analysis permission evidence")
    check = check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="analyze",
        source_content=notice,
    )
    if not check["allowed"]:
        raise ValueError("Unauthorized human model prediction")


def frozen_prediction(
    path: Path,
    identity: str,
    model: str,
    contract: dict[str, Any],
    X: Any,
    powers: Any,
    covariances: Any,
    *,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
) -> tuple[Any, Any, Any]:
    d = inspect_archive(path, identity)
    authorize(d, permission, notice)
    if d["dependency_versions"]["pyriemann"] != version("pyriemann"):
        raise ValueError("Unsupported numerical dependency environment")
    validate_contract(contract)
    if not compatibility(d["contract"], contract)["exact"] or model not in MODELS:
        raise ValueError("Incompatible transfer contract or decoder")
    if any(np.asarray(a).dtype != np.dtype("float64") for a in [X, powers, covariances]):
        raise ValueError("Frozen float64 numerical input required")
    row = d["models"][model]
    return predict(
        safe_reference(archive_root(path), row["file"]), row["id"], contract, X, powers, covariances
    )


def verify_release(
    path: Path,
    identity: str,
    probe: Path,
    *,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
) -> dict[str, Any]:
    d = inspect_archive(path, identity)
    authorize(d, permission, notice)
    if sha256(probe) != d["probe_sha256"]:
        raise ValueError("Prediction probe identity mismatch")
    e, a = load_result(probe)
    if e["method"] != {"id": "soma.model-probe", "version": "1"} or e["payload"]["values"] != {
        "protocol_fingerprint": d["protocol_fingerprint"],
        "source_fingerprint": d["source_fingerprint"],
    }:
        raise ValueError("Probe/protocol/input mismatch")
    reports = {}
    for model in MODELS:
        label, score, proba = frozen_prediction(
            path,
            identity,
            model,
            d["contract"],
            a["X"],
            a["powers"],
            a["covariances"],
            permission=permission,
            notice=notice,
        )
        if not np.array_equal(label, a[model + "_labels"]):
            raise ValueError("Frozen labels differ from training-session predictions")
        values = {
            "labels_exact": True,
            "scores_exact": bool(np.array_equal(score, a[model + "_scores"])),
            "score_max_abs_error": float(np.max(np.abs(score - a[model + "_scores"]))),
        }
        np.testing.assert_allclose(score, a[model + "_scores"], **d["tolerance"])
        if proba is not None:
            np.testing.assert_allclose(proba, a[model + "_probabilities"], **d["tolerance"])
            values["probability_max_abs_error"] = float(
                np.max(np.abs(proba - a[model + "_probabilities"]))
            )
        reports[model] = values
    return {
        "schema": "soma.model-reload/1",
        "release_id": identity,
        "manifest_sha256": sha256(path),
        "status": "VERIFIED",
        "models": reports,
        "environment": environment_snapshot(),
        "no_estimator_object_loaded": True,
        "external_replication": False,
        "n_predictions_per_model": len(a["X"]),
    }


def aggregate_summary(
    path: Path,
    identity: str,
    reload_receipt: Path,
    *,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
) -> dict[str, Any]:
    """Whitelist aggregate facts; no model arrays or participant rows are exported."""
    d = inspect_archive(path, identity)
    authorize(d, permission, notice)
    if d["dataset"] == "eegmmidb":
        assert permission is not None and notice is not None
        allowed = check_permission(
            permission,
            dataset="eegmmidb",
            version="1.0.0",
            purpose="methods_research",
            action="export_aggregate",
            source_content=notice,
        )
        if not allowed["allowed"]:
            raise ValueError("Aggregate model evidence export is not authorized")
    envelope, arrays = load_result(reload_receipt)
    check = envelope["payload"]["values"]
    if (
        arrays
        or envelope["method"] != {"id": "soma.model-reload", "version": "1"}
        or check["release_id"] != identity
        or check["manifest_sha256"] != sha256(path)
        or check["status"] != "VERIFIED"
        or set(check["models"]) != set(MODELS)
        or not all(row["labels_exact"] for row in check["models"].values())
    ):
        raise ValueError("Release reload verification is missing or inconsistent")
    validation, numeric = load_result(archive_root(path) / "source-validation/result.json")
    if numeric or validation["method"] != {"id": "soma.model-source-validation", "version": "1"}:
        raise ValueError("Source validation unavailable")
    methods = [
        {k: v for k, v in row.items() if k != "units"}
        for row in validation["payload"]["values"]["validation"]["methods"]
    ]
    c = d["cohort"]
    return {
        "schema": "soma.model-release-summary/1",
        "status": "VERIFIED_NEW_SOURCE_RELEASE"
        if d["dataset"] == "eegmmidb"
        else "SYNTHETIC_REFERENCE_ONLY",
        "release_id": identity,
        "protocol_fingerprint": d["protocol_fingerprint"],
        "training_cohort": (
            f"{c['eligible_subjects']}/{c['planned_subjects']} source participants; "
            f"{c['recordings']} recordings; {c['trials']} trials"
        ),
        "models": list(MODELS),
        "fitted_state": "All five complete numeric states and reload predictions verified",
        "source_validation": {
            "methods": methods,
            "sampling_unit": "subject",
            "external_replication": False,
        },
        "external_acquisition": "EXTERNAL_DATA_ACQUISITION_BLOCKED",
        "human_external_accuracy": None,
        "historical_m22": False,
        "warnings": [
            "Newly fitted state; not original M22 weights",
            "Historically reused source cohort and parameter choices",
            "Subject-fold intervals are conditional descriptive summaries",
            "No external human accuracy, confidence interval or p-value",
            "Weights remain private; integrity is not independent validation",
        ],
    }
