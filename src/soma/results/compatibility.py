"""Field-specific scientific compatibility; no estimator or implicit conversion."""

import copy
from typing import Any

import numpy as np

from soma.results.contracts import UNITS, SchemaError, seal, validate_result
from soma.sdk.provenance import array_fingerprint

SEMANTICS = [
    "result_kind",
    "dataset_identity",
    "subject_identity",
    "statistical_estimand",
    "method",
    "parameters",
    "spatial_reference",
    "temporal_reference",
]


def compare_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    validate_result(left)
    validate_result(right)
    issues = []
    unknown = []
    conversions = {}
    for key in SEMANTICS:
        if key not in left or key not in right:
            unknown.append(
                {"field": key, "reason": "Unrecorded metadata; equality cannot be established"}
            )
        elif left[key] != right[key]:
            issues.append(
                {"field": key, "reason": "Different scientific definitions or identities"}
            )
    # Domain contracts carry montage, task, ontology, preprocessing, contrast,
    # correction, grid, forward/inverse identity and all declared assumptions.
    ld, rd = left["payload"]["domain"], right["payload"]["domain"]
    for key in sorted(set(ld) | set(rd)):
        if key not in ld or key not in rd:
            unknown.append(
                {"field": "domain." + key, "reason": "Definition was not recorded in both results"}
            )
        elif ld[key] != rd[key]:
            issues.append(
                {"field": "domain." + key, "reason": "Different domain assumptions/definitions"}
            )
    lu, ru = left.get("units"), right.get("units")
    if lu is None or ru is None:
        unknown.append({"field": "units", "reason": "Unknown units"})
    elif set(lu) != set(ru):
        issues.append({"field": "units", "reason": "Different physical quantities"})
    else:
        for quantity in lu:
            if UNITS[lu[quantity]][0] != UNITS[ru[quantity]][0]:
                issues.append(
                    {"field": "units." + quantity, "reason": "Different physical dimensions"}
                )
            elif lu[quantity] != ru[quantity]:
                conversions[quantity] = UNITS[lu[quantity]][1] / UNITS[ru[quantity]][1]
    if left["result_kind"] == "legacy.record" or any(
        x["interpretation_state"] in {"INVALID", "INDETERMINATE", "NOT_AVAILABLE"}
        for x in [left, right]
    ):
        unknown.append(
            {
                "field": "interpretation_state",
                "reason": "Insufficient or unavailable scientific interpretation",
            }
        )
    status = (
        "INCOMPATIBLE"
        if issues
        else "INDETERMINATE"
        if unknown
        else "CONVERTIBLE"
        if conversions
        else "COMPATIBLE"
    )
    return {
        "status": status,
        "compatible": status == "COMPATIBLE",
        "issues": issues,
        "unknown": unknown,
        "left_to_right_unit_factors": conversions,
        "scientific_validity": "NOT_ESTABLISHED_BY_COMPATIBILITY",
        "conversion_performed": False,
    }


def require_compatible(left: dict[str, Any], right: dict[str, Any]) -> None:
    result = compare_results(left, right)
    if not result["compatible"]:
        raise SchemaError(str(result))


def convert_units(
    value: dict[str, Any], arrays: dict[str, Any], *, target: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Explicit PSD/power SI-prefix conversion only; never frames or estimands.

    Summary values are rejected because their unit semantics are not modeled.
    Output is a new, unpersisted artifact requiring save_result to hash file bytes.
    """
    validate_result(value, arrays)
    kind = value["result_kind"]
    field = (
        "density" if kind == "eeg.spectrum" else "power" if kind == "eeg.time_frequency" else None
    )
    if field is None or value["payload"]["values"] is not None:
        raise SchemaError(
            "No justified conversion adapter for this payload; "
            "recomputation/explicit modeling required"
        )
    source = value["units"][field]
    if target not in UNITS or UNITS[source][0] != UNITS[target][0]:
        raise SchemaError("Unit dimensions/estimands cannot be converted")
    factor = UNITS[source][1] / UNITS[target][1]
    output = copy.deepcopy(value)
    data = {k: np.array(a, copy=True) for k, a in arrays.items()}
    data[field] = np.asarray(data[field], dtype=np.float64) * factor
    output["units"][field] = target
    output["payload"]["arrays"][field].update(
        dtype=data[field].dtype.str, content_sha256=array_fingerprint(data[field])
    )
    output["checksums"]["arrays"] = {}
    output["provenance"].setdefault("unit_conversions", []).append(
        {
            "quantity": field,
            "source": source,
            "target": target,
            "factor": factor,
            "source_metadata_sha256": value["checksums"]["metadata"],
        }
    )
    output = seal(output)
    validate_result(output, data)
    return output, data
