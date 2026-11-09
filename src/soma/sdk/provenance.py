"""Small metadata extensions to the existing Soma manifest, not an inference engine."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np

from soma.core.provenance import manifest as manifest
from soma.core.provenance import sha256 as sha256
from soma.core.provenance import write_json as write_json


def array_fingerprint(array: Any) -> str:
    """SHA256 of dtype, shape and C-order bytes; no rounding or subject inference."""
    a = np.asarray(array)
    if a.dtype.kind not in "biuf" or not np.isfinite(a).all():
        raise ValueError("Finite real numerical array required")
    header = json.dumps([a.dtype.str, list(a.shape)], separators=(",", ":")).encode()
    return hashlib.sha256(header + b"\0" + a.tobytes(order="C")).hexdigest()


def result_metadata(
    *,
    input_fingerprint: str,
    method: str,
    parameters: dict[str, Any],
    units: str,
    data_identity: str,
    estimand: str,
    spatial_reference: str | None,
    interpretation: Literal["synthetic", "descriptive", "unavailable"],
    warnings: list[str],
    source: dict[str, Any],
    seed: int | None = None,
) -> dict[str, Any]:
    """Extend manifest with explicit result semantics. This cannot authorize inference.

    Spatial results require a nonempty caller-declared reference; nonspatial
    results explicitly use None. Do not put participant IDs or private paths in
    shared metadata. Warnings are required, including an explicitly empty list.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", input_fingerprint):
        raise ValueError("A lowercase SHA256 input fingerprint is required")
    if not all(isinstance(x, str) and x.strip() for x in [method, units, data_identity, estimand]):
        raise ValueError("Method, units, data identity and estimand are required")
    if spatial_reference is not None and not spatial_reference.strip():
        raise ValueError("Spatial reference cannot be empty")
    if interpretation not in {"synthetic", "descriptive", "unavailable"}:
        raise ValueError("Metadata cannot authorize confirmatory inference")
    if not source or any(not isinstance(x, str) or not x for x in warnings):
        raise ValueError("Explicit source provenance and string warnings required")
    result = manifest(source, parameters, {}, seed)
    result.update(
        {
            "sdk_schema_version": 1,
            "input_fingerprint": input_fingerprint,
            "method": method,
            "units": units,
            "data_identity": data_identity,
            "estimand": estimand,
            "spatial_reference": spatial_reference,
            "interpretation": interpretation,
            "warnings": warnings,
            "confirmatory_claim_allowed": False,
        }
    )
    # Copy through strict JSON to reject NaN and borrowed/nonserializable objects.
    return cast(dict[str, Any], json.loads(json.dumps(result, allow_nan=False)))


def require_comparable(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Conservative same-data comparison; ontology/contrast belong in parameters.

    Different fingerprints may describe independent predictions, but matching
    identity, semantics, methods and parameters are mandatory. No pooling implied.
    """
    for key in [
        "sdk_schema_version",
        "application_version",
        "method",
        "units",
        "data_identity",
        "estimand",
        "spatial_reference",
        "interpretation",
        "parameters",
    ]:
        if key not in left or key not in right or left[key] != right[key]:
            raise ValueError(f"Incompatible or missing result field: {key}")


def read_manifest(path: Path) -> dict[str, Any]:
    """Read existing strict JSON provenance. No reconstruction of missing fields."""
    value = json.loads(
        path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))
    )
    if not isinstance(value, dict):
        raise ValueError("Manifest must be a JSON object")
    return value
