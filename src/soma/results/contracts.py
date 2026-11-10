"""Strict shared envelopes and representative domain contracts, without estimators."""

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any

import numpy as np

from soma import __version__
from soma.sdk.provenance import array_fingerprint

SCHEMA = "soma.result"
CURRENT = "1.1.0"
VERSIONS = {"1.0.0", "1.1.0"}
STATES = {
    "VALIDATED_NUMERICAL",
    "DESCRIPTIVE_ONLY",
    "EXPLORATORY",
    "INDETERMINATE",
    "INVALID",
    "NOT_AVAILABLE",
}
BASE = {
    "schema_name",
    "schema_version",
    "producer",
    "producer_version",
    "result_kind",
    "interpretation_state",
    "provenance",
    "payload",
    "checksums",
}
OPTIONAL = {
    "created_at",
    "dataset_identity",
    "subject_identity",
    "method",
    "parameters",
    "units",
    "spatial_reference",
    "temporal_reference",
    "statistical_estimand",
    "warnings",
    "migration",
}
# Domain dictionaries are closed. Scientific inputs are declared, never inferred.
DOMAINS: dict[str, tuple[set[str], set[str]]] = {
    "eeg.spectrum": (
        {"fs_hz", "channels", "reference", "window", "psd_config"},
        {"task", "events"},
    ),
    "eeg.time_frequency": (
        {"fs_hz", "channels", "reference", "window", "tf_config"},
        {"task", "events"},
    ),
    "eeg.bursts": (
        {"fs_hz", "channels", "reference", "window", "thresholds", "interval_convention"},
        {"task", "events"},
    ),
    "mri.geometry": ({"image_identity", "shape", "affine", "spacing", "grid_identity"}, set()),
    "mri.segmentation": (
        {
            "image_identity",
            "grid_identity",
            "ontology",
            "label_correspondence",
            "boundary_definition",
        },
        set(),
    ),
    "mri.surface": ({"geometry_identity", "frame", "surface_semantics"}, {"topology_checks"}),
    "mri.registration": (
        {"fixed_identity", "moving_identity", "transform_direction", "frame"},
        {"diagnostics"},
    ),
    "source.reconstruction": (
        {
            "source_space_identity",
            "forward_identity",
            "inverse_identity",
            "regularization",
            "conductivity_S_m",
            "anatomical_readiness",
            "resolution_definition",
        },
        set(),
    ),
    "fmri.contrast": (
        {
            "session",
            "task",
            "run",
            "tr_s",
            "design_identity",
            "contrast",
            "noise_model",
            "inference_policy",
            "correction",
            "preprocessing",
        },
        set(),
    ),
    "fmri.roi": (
        {
            "session",
            "task",
            "run",
            "tr_s",
            "design_identity",
            "contrast",
            "noise_model",
            "inference_policy",
            "correction",
            "preprocessing",
            "roi_ontology",
            "roi_space",
        },
        set(),
    ),
    "experiment.manifest": (
        {"computation", "inputs", "environment", "assumptions", "validation", "limitations"},
        set(),
    ),
    "legacy.record": ({"legacy_format", "missing_metadata"}, set()),
}
UNITS = {
    "1": ("dimensionless", 1.0),
    "probability": ("probability", 1.0),
    "V": ("voltage", 1.0),
    "uV": ("voltage", 1e-6),
    "V^2": ("power", 1.0),
    "uV^2": ("power", 1e-12),
    "V^2/Hz": ("density", 1.0),
    "uV^2/Hz": ("density", 1e-12),
    "Hz": ("frequency", 1.0),
    "s": ("time", 1.0),
    "m": ("length", 1.0),
    "mm": ("length", 0.001),
    "m^2": ("area", 1.0),
    "mm^2": ("area", 1e-6),
    "m^3": ("volume", 1.0),
    "mm^3": ("volume", 1e-9),
    "A*m": ("dipole", 1.0),
    "nA*m": ("dipole", 1e-9),
    "BOLD/regressor": ("BOLD_effect", 1.0),
    "(BOLD/regressor)^2": ("BOLD_variance", 1.0),
}
UNIT_KEYS = {
    "eeg.spectrum": {"density": "density", "frequency": "frequency"},
    "eeg.time_frequency": {"power": "power", "frequency": "frequency", "time": "time"},
    "eeg.bursts": {"amplitude": "voltage", "time": "time"},
    "mri.geometry": {"length": "length"},
    "mri.segmentation": {"overlap": "dimensionless", "distance": "length", "volume": "volume"},
    "mri.surface": {"length": "length", "area": "area", "volume": "volume"},
    "mri.registration": {"length": "length"},
    "source.reconstruction": {"amplitude": "dipole", "length": "length"},
    "fmri.contrast": {
        "effect": "BOLD_effect",
        "variance": "BOLD_variance",
        "statistic": "dimensionless",
    },
    "fmri.roi": {"effect": "BOLD_effect"},
}
ARRAYS = {
    "eeg.spectrum": {"frequencies": 1, "density": 2},
    "eeg.time_frequency": {"frequencies": 1, "times": 1, "power": 4, "valid": 2},
    "eeg.bursts": {"intervals": 2},
    "source.reconstruction": {"amplitudes": 2},
    "mri.registration": {"transform": 2},
}
HEX = re.compile(r"[0-9a-f]{64}")


class SchemaError(ValueError):
    """Invalid/unsupported artifact; never a statement of scientific invalidity."""


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError) as error:
        raise SchemaError("Strict finite JSON required") from error


def metadata_digest(value: dict[str, Any]) -> str:
    v = copy.deepcopy(value)
    v["checksums"].pop("metadata", None)
    return hashlib.sha256(canonical(v)).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Explicitly reseal metadata after an intentional edit; not authentication."""
    v = copy.deepcopy(value)
    v["checksums"]["metadata"] = metadata_digest(v)
    return v


def _closed(value: Any, required: set[str], optional: set[str], field: str) -> None:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise SchemaError(f"{field}: missing or unknown fields")


def _validate_result(value: dict[str, Any], arrays: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate format and declared numerical contracts. No statistical/anatomical certification."""
    if len(canonical(value)) > 2 * 1024**2:
        raise SchemaError("Envelope exceeds metadata bound")
    _closed(value, BASE, OPTIONAL, "envelope")
    if value["schema_name"] != SCHEMA or value["schema_version"] not in VERSIONS:
        raise SchemaError("Unsupported schema name/version; use an explicit supported adapter")
    if value["schema_version"] == "1.0.0" and {"warnings", "migration"} & value.keys():
        raise SchemaError("warnings/migration require schema 1.1.0")
    kind = value["result_kind"]
    if kind not in DOMAINS or value["interpretation_state"] not in STATES:
        raise SchemaError("Unsupported result kind or interpretation state")
    for key in ["producer", "producer_version"]:
        if not isinstance(value[key], str) or not value[key]:
            raise SchemaError(f"Missing {key}")
    if "created_at" in value and value["created_at"] is not None:
        try:
            parsed = datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone")
        except (ValueError, TypeError, AttributeError) as error:
            raise SchemaError("created_at requires a known timezone-aware ISO timestamp") from error
    for key in ["dataset_identity", "subject_identity", "statistical_estimand"]:
        if (
            key in value
            and value[key] is not None
            and (not isinstance(value[key], str) or not value[key])
        ):
            raise SchemaError(f"Invalid {key}")
    if not isinstance(value["provenance"], dict):
        raise SchemaError("Provenance dictionary required")
    _closed(value["payload"], {"domain", "arrays", "values"}, set(), "payload")
    domain = value["payload"]["domain"]
    required_domain, optional_domain = DOMAINS[kind]
    if kind.startswith("eeg.") and value["interpretation_state"] == "INDETERMINATE":
        required_domain = required_domain - {"reference"}
        optional_domain = optional_domain | {"reference"}
    _closed(domain, required_domain, optional_domain, "domain")
    if kind != "legacy.record":
        for key in ["method", "parameters", "units"]:
            if key not in value:
                raise SchemaError(f"Required scientific metadata: {key}")
        _closed(value["method"], {"id", "version"}, set(), "method")
        if any(not isinstance(x, str) or not x for x in value["method"].values()):
            raise SchemaError("Explicit method identity/version required")
        if not isinstance(value["parameters"], dict):
            raise SchemaError("parameters must be a dictionary")
    units = value.get("units", {})
    if not isinstance(units, dict) or any(u not in UNITS for u in units.values()):
        raise SchemaError("Unknown physical unit")
    if kind in UNIT_KEYS:
        if set(units) != set(UNIT_KEYS[kind]) or any(
            UNITS[units[k]][0] != dim for k, dim in UNIT_KEYS[kind].items()
        ):
            raise SchemaError("Unit dimensions do not match result kind")
    spatial = value.get("spatial_reference")
    if spatial is not None:
        _closed(spatial, {"frame", "space", "unit"}, {"grid_identity"}, "spatial_reference")
        if (
            spatial["frame"] not in {"RAS", "LPS", "HEAD", "MRI", "TEMPLATE_MRI"}
            or spatial["unit"] not in {"m", "mm"}
            or not spatial["space"]
        ):
            raise SchemaError("Invalid coordinate frame/space/units")
        if "length" in units and units["length"] != spatial["unit"]:
            raise SchemaError("Spatial length units disagree")
    if (kind.startswith("mri.") or kind.startswith("source.")) and spatial is None:
        raise SchemaError("Explicit spatial reference required")
    if kind.startswith("fmri.") and (
        spatial is None
        or not value.get("subject_identity")
        or not value.get("statistical_estimand")
    ):
        raise SchemaError("fMRI requires subject, spatial reference and estimand")
    temporal = value.get("temporal_reference")
    if temporal is not None:
        _closed(
            temporal,
            set(),
            {"fs_hz", "tr_s", "time_origin_s", "window_definition"},
            "temporal_reference",
        )
        for key in ["fs_hz", "tr_s"]:
            if key in temporal and (
                not isinstance(temporal[key], (float, int)) or temporal[key] <= 0
            ):
                raise SchemaError("Invalid temporal sampling")
    if kind.startswith("eeg."):
        if (
            not isinstance(domain["fs_hz"], (int, float))
            or domain["fs_hz"] <= 0
            or not domain["channels"]
            or len(set(domain["channels"])) != len(domain["channels"])
        ):
            raise SchemaError("Positive sampling and unique channel identities required")
        if not isinstance(domain["window"], dict):
            raise SchemaError("Explicit window definitions required")
        if kind == "eeg.spectrum":
            _closed(
                domain["psd_config"],
                {"nperseg", "noverlap", "window", "average", "scaling", "sidedness"},
                set(),
                "psd_config",
            )
            c = domain["psd_config"]
            if (
                c["scaling"] != "density"
                or c["sidedness"] != "one-sided"
                or not isinstance(c["nperseg"], int)
                or not 0 <= c["noverlap"] < c["nperseg"]
            ):
                raise SchemaError("Invalid PSD definition")
        if kind == "eeg.bursts" and domain["interval_convention"] != "half-open seconds":
            raise SchemaError("Unsupported burst interval convention")
    if kind == "eeg.time_frequency":
        _closed(
            domain["tf_config"],
            {"frequencies_hz", "n_cycles", "power_definition"},
            set(),
            "tf_config",
        )
        if domain["tf_config"]["n_cycles"] <= 0:
            raise SchemaError("Positive wavelet cycles required")
    if kind == "eeg.bursts":
        _closed(
            domain["thresholds"],
            {"low", "high", "minimum_duration_s", "calibration", "filter"},
            set(),
            "thresholds",
        )
        if (
            not 0 < domain["thresholds"]["low"] <= domain["thresholds"]["high"]
            or domain["thresholds"]["minimum_duration_s"] <= 0
        ):
            raise SchemaError("Invalid burst thresholds/duration")
    if kind == "source.reconstruction":
        if (
            not domain["source_space_identity"]
            or not domain["forward_identity"]
            or not domain["inverse_identity"]
        ):
            raise SchemaError("Source/operator identities required")
        if (
            not isinstance(domain["regularization"], dict)
            or domain["regularization"].get("lambda2", -1) < 0
        ):
            raise SchemaError("Explicit nonnegative inverse regularization required")
        if not domain["conductivity_S_m"] or any(c <= 0 for c in domain["conductivity_S_m"]):
            raise SchemaError("Positive conductivity assumptions required")
    if kind == "mri.registration" and domain["transform_direction"] != "reference_to_source":
        raise SchemaError("Registration requires explicit pull mapping")
    if kind in {"mri.surface", "mri.registration"}:
        if not isinstance(spatial, dict) or domain["frame"] != spatial["frame"]:
            raise SchemaError("Domain and spatial reference frames disagree")
    if kind == "source.reconstruction" and domain["anatomical_readiness"] not in {
        "INDETERMINATE",
        "NOT_ASSESSED",
        "FAILED",
        "CONDITIONAL_RESEARCH",
    }:
        raise SchemaError("Schema does not establish anatomical readiness")
    if kind == "experiment.manifest":
        if not isinstance(domain["inputs"], dict):
            raise SchemaError("Manifest input hash mapping required")
        for ref, digest in domain["inputs"].items():
            if (
                not isinstance(ref, str)
                or ref.startswith("/")
                or ".." in ref.split("/")
                or "\\" in ref
                or ":" in ref
                or not HEX.fullmatch(digest)
            ):
                raise SchemaError("Portable relative input references and SHA256 required")
    if kind.startswith("eeg."):
        channels = domain["channels"]
        if not isinstance(channels, list) or any(not isinstance(c, str) or not c for c in channels):
            raise SchemaError("Channel identities must be nonempty strings")
        if (
            "reference" in domain
            and domain["reference"] is not None
            and (not isinstance(domain["reference"], str) or not domain["reference"])
        ):
            raise SchemaError("Reference must be explicit text or known-inapplicable null")
    if kind == "mri.geometry":
        a = np.asarray(domain["affine"], dtype=float)
        spacing = np.asarray(domain["spacing"], dtype=float)
        if (
            a.shape != (4, 4)
            or not np.isfinite(a).all()
            or not np.allclose(a[3], [0, 0, 0, 1])
            or abs(np.linalg.det(a[:3, :3])) < 1e-18
        ):
            raise SchemaError("Invalid voxel-to-world affine")
        if len(domain["shape"]) != 3 or any(
            not isinstance(n, int) or n < 1 for n in domain["shape"]
        ):
            raise SchemaError("Invalid voxel grid")
        if (
            spacing.shape != (3,)
            or np.any(spacing <= 0)
            or not np.allclose(np.linalg.norm(a[:3, :3], axis=0), spacing)
        ):
            raise SchemaError("Spacing/affine mismatch")
    if kind in {"mri.segmentation", "fmri.roi"}:
        ontology = domain["ontology"] if kind == "mri.segmentation" else domain["roi_ontology"]
        if (
            not isinstance(ontology, dict)
            or not ontology
            or any(
                not str(k).isdigit() or not isinstance(n, str) or not n for k, n in ontology.items()
            )
        ):
            raise SchemaError("Explicit discrete label ontology required")
    if kind.startswith("fmri."):
        policy = domain["inference_policy"]
        if not isinstance(policy, dict) or policy.get("confirmatory_claim_allowed") is not False:
            raise SchemaError("Schema cannot authorize confirmatory fMRI inference")
        if (
            domain["tr_s"] <= 0
            or not isinstance(domain["contrast"], dict)
            or not domain["contrast"]
            or not any(domain["contrast"].values())
            or domain["correction"] not in {"bh", "by", "bonferroni"}
            or domain["noise_model"] not in {"ols", "ar1", "ar2"}
        ):
            raise SchemaError("Invalid fMRI model contract")
        if value["interpretation_state"] not in {
            "DESCRIPTIVE_ONLY",
            "EXPLORATORY",
            "INDETERMINATE",
        }:
            raise SchemaError("fMRI interpretation remains descriptive")
    descriptors = value["payload"]["arrays"]
    if not isinstance(descriptors, dict) or len(descriptors) > 32:
        raise SchemaError("Bounded array mapping required")
    required = ARRAYS.get(kind, {})
    if not required.keys() <= descriptors.keys():
        raise SchemaError("Required numerical arrays missing")
    for name, d in descriptors.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name):
            raise SchemaError("Unsafe array identity")
        _closed(d, {"file", "dtype", "shape", "content_sha256"}, set(), "array descriptor")
        if d["file"] != f"arrays/{name}.npy" or not HEX.fullmatch(d["content_sha256"]):
            raise SchemaError("Unsafe array reference or fingerprint")
        try:
            dt = np.dtype(d["dtype"])
        except (TypeError, ValueError) as error:
            raise SchemaError("Invalid dtype") from error
        if (
            dt.kind not in "biuf"
            or dt.itemsize > 8
            or not isinstance(d["shape"], list)
            or len(d["shape"]) > 5
            or any(type(n) is not int or n < 0 for n in d["shape"])
        ):
            raise SchemaError("Unsupported numeric array dtype/shape")
        count = 1
        for n in d["shape"]:
            count *= n
        if count * dt.itemsize > 64 * 1024**2:
            raise SchemaError("Declared array allocation exceeds bound")
        if name in required and len(d["shape"]) != required[name]:
            raise SchemaError("Wrong array dimensions")
        if arrays is not None:
            if name not in arrays:
                raise SchemaError("Numerical payload missing")
            a = np.asarray(arrays[name])
            if (
                list(a.shape) != d["shape"]
                or a.dtype.str != d["dtype"]
                or not np.isfinite(a).all()
                or array_fingerprint(a) != d["content_sha256"]
            ):
                raise SchemaError("Array shape/dtype/finiteness/fingerprint mismatch")
    if kind == "eeg.spectrum":
        nfreq = descriptors["frequencies"]["shape"][0]
        if (
            descriptors["density"]["shape"] != [len(domain["channels"]), nfreq]
            or nfreq != domain["psd_config"]["nperseg"] // 2 + 1
        ):
            raise SchemaError("Metadata PSD axes/configuration mismatch")
    if kind == "eeg.time_frequency":
        nf = descriptors["frequencies"]["shape"][0]
        nt = descriptors["times"]["shape"][0]
        if (
            descriptors["power"]["shape"][1:] != [len(domain["channels"]), nf, nt]
            or descriptors["valid"]["shape"] != [nf, nt]
            or len(domain["tf_config"]["frequencies_hz"]) != nf
        ):
            raise SchemaError("Metadata time-frequency axes mismatch")
    if kind == "eeg.bursts" and descriptors["intervals"]["shape"][1] != 2:
        raise SchemaError("Burst intervals need start/stop columns")
    if arrays is not None:
        if set(arrays) != set(descriptors):
            raise SchemaError("Unexpected array payload")
        if kind.startswith("eeg.") and "frequencies" in arrays:
            f = arrays["frequencies"]
            if len(f) < 2 or np.any(np.diff(f) <= 0) or f[0] < 0 or f[-1] > domain["fs_hz"] / 2:
                raise SchemaError("Invalid frequency axis")
        if kind == "eeg.spectrum":
            if arrays["density"].shape != (
                len(domain["channels"]),
                len(arrays["frequencies"]),
            ) or np.any(arrays["density"] < 0):
                raise SchemaError("PSD channel/frequency alignment or sign invalid")
        if kind == "eeg.time_frequency":
            expected = (len(domain["channels"]), len(arrays["frequencies"]), len(arrays["times"]))
            if (
                arrays["power"].shape[1:] != expected
                or arrays["valid"].shape != expected[1:]
                or np.any(np.diff(arrays["times"]) <= 0)
                or arrays["valid"].dtype.kind != "b"
            ):
                raise SchemaError("Time-frequency axes/mask mismatch")
        if kind == "eeg.bursts" and (
            arrays["intervals"].shape[1] != 2
            or np.any(arrays["intervals"][:, 1] <= arrays["intervals"][:, 0])
        ):
            raise SchemaError("Invalid burst intervals")
        if kind == "mri.registration" and arrays["transform"].shape != (4, 4):
            raise SchemaError("Registration transform must be 4x4")
    _closed(value["checksums"], {"metadata", "arrays"}, set(), "checksums")
    if value["checksums"]["metadata"] != metadata_digest(value):
        raise SchemaError("Metadata checksum mismatch")
    if (
        not isinstance(value["checksums"]["arrays"], dict)
        or set(value["checksums"]["arrays"]) - set(descriptors)
        or any(not HEX.fullmatch(h) for h in value["checksums"]["arrays"].values())
    ):
        raise SchemaError("Invalid array checksums")
    return {
        "format": "VALID",
        "schema_version": value["schema_version"],
        "numerical_payload_checked": arrays is not None,
        "scientific_validation": "NOT_ESTABLISHED_BY_SCHEMA",
    }


def create_result(
    kind: str,
    domain: dict[str, Any],
    *,
    arrays: dict[str, Any] | None = None,
    values: Any = None,
    interpretation_state: str = "EXPLORATORY",
    provenance: dict[str, Any],
    **metadata: Any,
) -> dict[str, Any]:
    """Create an envelope from explicit metadata; no timestamps/identities are inferred."""
    if set(metadata) & BASE:
        raise SchemaError("Common envelope fields cannot be overridden")
    payload_arrays = arrays or {}
    result = {
        "schema_name": SCHEMA,
        "schema_version": CURRENT,
        "producer": "soma-neuro",
        "producer_version": __version__,
        "result_kind": kind,
        "interpretation_state": interpretation_state,
        "provenance": copy.deepcopy(provenance),
        "payload": {
            "domain": copy.deepcopy(domain),
            "values": copy.deepcopy(values),
            "arrays": {
                name: {
                    "file": f"arrays/{name}.npy",
                    "dtype": np.asarray(a).dtype.str,
                    "shape": list(np.asarray(a).shape),
                    "content_sha256": array_fingerprint(a),
                }
                for name, a in payload_arrays.items()
            },
        },
        "checksums": {"arrays": {}},
        **copy.deepcopy(metadata),
    }
    result = seal(result)
    validate_result(result, payload_arrays)
    return result


def upgrade_schema(value: dict[str, Any]) -> dict[str, Any]:
    """Explicit 1.0→1.1 metadata-only upgrade; payload/provenance bytes are retained."""
    validate_result(value)
    if value["schema_version"] == CURRENT:
        return copy.deepcopy(value)
    result = copy.deepcopy(value)
    result["schema_version"] = CURRENT
    result["migration"] = {
        "source_schema_version": "1.0.0",
        "software_version": __version__,
        "operation": "metadata-only version upgrade; no numerical reinterpretation",
    }
    return seal(result)


def validate_result(value: dict[str, Any], arrays: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate supported format/domain contracts; invalid types fail as SchemaError."""
    try:
        return _validate_result(value, arrays)
    except (TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
        raise SchemaError("Malformed scientific metadata types or dimensions") from error
