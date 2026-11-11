"""Bounded M17 numeric model capsules; no pickle, fitting on import, or M22 forgery."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from pyriemann.geometry.tangentspace import tangent_space
from scipy.special import expit

from soma.decoding.covariance import require_spd
from soma.decoding.riemannian import riemannian_distance
from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.eeg_benchmark.protocol import MODELS
from soma.external_eeg.contracts import compatibility, validate_contract
from soma.pipeline.cache import source_hash
from soma.results.contracts import create_result
from soma.results.io import inspect_result, load_result, save_result
from soma.sdk.provenance import array_fingerprint
from soma.workflow.model import digest


def freeze(
    pipeline: Any,
    model: str,
    contract: dict[str, Any],
    training: dict[str, Any],
    output: Path,
    *,
    prior: float | None = None,
) -> str:
    validate_contract(contract)
    if model not in MODELS or training.get("origin") not in (
        "SYNTHETIC_SOURCE_FIT",
        "EXTERNAL_SOURCE_REFIT",
        "EEGBCI_PROSPECTIVE_SOURCE_FIT",
    ):
        raise ValueError("Newly fitted models cannot masquerade as original M22 artifacts")
    arrays: dict[str, Any] = {}
    if model == "dummy":
        if prior is None or not 0 <= prior <= 1:
            raise ValueError("Training prior required")
        arrays["prior"] = np.array([prior])
    else:
        steps = pipeline.named_steps
        classifier = steps["classifier"]
        if not np.array_equal(classifier.classes_, [0, 1]):
            raise ValueError("Class ordering changed")
        if "scale" in steps:
            arrays.update(mean=steps["scale"].mean_, scale=steps["scale"].scale_)
        if model == "csp_lda":
            arrays["filters"] = steps["csp"].filters_[: steps["csp"].n_components]
        if model == "riemann_mdm":
            arrays["means"] = classifier.model_.covmeans_
        else:
            arrays.update(coef=classifier.coef_, intercept=classifier.intercept_)
        if model == "tangent_lr":
            arrays["reference"] = steps["tangent"].reference_
    metadata = {
        "model": model,
        "contract": contract,
        "training": training,
        "environment": environment_snapshot(),
        "original_m22": False,
        "implementation": source_hash(),
    }
    identity = digest(
        {
            "metadata": metadata,
            "arrays": {k: array_fingerprint(np.asarray(a)) for k, a in arrays.items()},
        }
    )
    value = create_result(
        "experiment.manifest",
        {
            "computation": "external-eeg-model-capsule",
            "inputs": {},
            "environment": environment_snapshot(),
            "assumptions": ["source-only fitted state"],
            "validation": {"scope": "numeric state; not authenticated historical origin"},
            "limitations": ["Not an original M22 saved model"],
        },
        arrays=arrays,
        values={**metadata, "id": identity},
        provenance={},
        method={"id": "soma.external-eeg.model", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(value, arrays, output)
    import_model(output / "result.json", identity)
    return identity


def import_model(path: Path, expected_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    inspect_result(path)
    envelope, arrays = load_result(path)
    if envelope["method"] != {"id": "soma.external-eeg.model", "version": "1"}:
        raise ValueError("Unsupported model")
    d = dict(envelope["payload"]["values"])
    validate_contract(d["contract"])
    if d["original_m22"] is not False:
        raise ValueError("Unsubstantiated original M22 identity")
    metadata = {k: v for k, v in d.items() if k != "id"}
    identity = digest(
        {"metadata": metadata, "arrays": {k: array_fingerprint(a) for k, a in arrays.items()}}
    )
    if identity != expected_id or identity != d["id"]:
        raise ValueError("Corrupted or untrusted model identity")
    model = d["model"]
    c = len(d["contract"]["channels"])
    features = 2 * c if model == "multiband_lr" else c * (c + 1) // 2
    shapes: dict[str, tuple[int, ...]] = {}
    if model == "dummy":
        shapes = {"prior": (1,)}
    elif model == "riemann_mdm":
        shapes = {"means": (2, c, c)}
    else:
        if model == "csp_lda":
            features = 4
            shapes["filters"] = (4, c)
        if model == "tangent_lr":
            shapes["reference"] = (c, c)
        shapes.update(coef=(1, features), intercept=(1,))
        if model in ("multiband_lr", "tangent_lr"):
            shapes.update(mean=(features,), scale=(features,))
    if (
        model not in MODELS
        or set(arrays) != set(shapes)
        or any(arrays[k].shape != v for k, v in shapes.items())
    ):
        raise ValueError("Incompatible model feature shape")
    if "scale" in arrays and np.any(arrays["scale"] <= 0):
        raise ValueError("Invalid fitted scale")
    if "prior" in arrays and not 0 <= float(arrays["prior"][0]) <= 1:
        raise ValueError("Invalid prior")
    if "means" in arrays:
        require_spd(arrays["means"])
    if "reference" in arrays:
        require_spd(arrays["reference"][None])
    return d, arrays


def predict(
    path: Path, identity: str, contract: dict[str, Any], X: Any, powers: Any, covariances: Any
) -> tuple[Any, Any, Any]:
    d, a = import_model(path, identity)
    if not compatibility(d["contract"], contract)["exact"]:
        raise ValueError("Incompatible frozen feature contract")
    current_environment = environment_snapshot()
    archived_environment = d["environment"]

    # Threadpool enumeration order can change with library load order. The complete
    # set of reported backends still has to match, including versions and threading.
    def backend_inventory(env: dict[str, Any]) -> list[str]:
        return sorted(json.dumps(row, sort_keys=True) for row in env["backends"])

    if "backends" not in archived_environment or "backends" not in current_environment:
        raise ValueError("Missing numerical backend environment identity; cache reuse denied")
    expected_static = {k: v for k, v in archived_environment.items() if k != "backends"}
    current_static = {k: v for k, v in current_environment.items() if k != "backends"}
    backend_matches = backend_inventory(archived_environment) == backend_inventory(
        current_environment
    )
    if expected_static != current_static or not backend_matches:
        differences = sorted(
            key
            for key in set(archived_environment) | set(current_environment)
            if archived_environment.get(key) != current_environment.get(key)
        )
        backend_difference = (
            {
                "archived": backend_inventory(archived_environment),
                "current": backend_inventory(current_environment),
            }
            if "backends" in differences
            else None
        )
        raise ValueError(
            "Cross-environment import requires independent validation; cache reuse denied "
            f"(differing fields: {differences}, backends: {backend_difference})"
        )
    n = len(X)
    if not n or not np.isfinite(X).all() or not np.isfinite(powers).all():
        raise ValueError("Finite nonempty physical EEG/features required")
    if d["implementation"] != source_hash():
        raise ValueError("Model feature implementation changed; explicit validation required")
    model = d["model"]
    if np.asarray(X).shape[1:] != (len(contract["channels"]), 320):
        raise ValueError("Incompatible epochs")
    if np.asarray(powers).shape != (n, 9, 2) or np.asarray(covariances).shape != (n, 9, 9):
        raise ValueError("Incompatible feature ordering or covariance shape")
    if model == "dummy":
        score = np.full(n, a["prior"][0])
        return np.full(n, int(score[0] > 0.5)), score, score
    if model == "riemann_mdm":
        require_spd(covariances)
        distances = np.array([[riemannian_distance(x, m) for m in a["means"]] for x in covariances])
        return distances.argmin(axis=1), distances[:, 0] - distances[:, 1], None
    if model == "multiband_lr":
        z = np.asarray(powers).reshape(n, -1)
    elif model == "csp_lda":
        z = np.log(
            np.mean(np.einsum("kc,nct->nkt", a["filters"], np.asarray(X) * 1e6) ** 2, axis=2)
        )
    else:
        z = tangent_space(require_spd(covariances), a["reference"], metric="riemann")
    if "scale" in a:
        z = (z - a["mean"]) / a["scale"]
    score = (z @ a["coef"].T).ravel() + a["intercept"][0]
    return (score > 0).astype(int), score, expit(score)
