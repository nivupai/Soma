"""Sealed decoding specifications and exact numerical software identity."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

from soma.core.provenance import sha256
from soma.experiments.cache import software_identity

MODELS = (
    "motor_mu_lr",
    "motor_bands_lda",
    "multiband_lr",
    "burst_lr",
    "csp_lda",
    "covariance_lda",
    "euclidean_mdm",
    "riemann_mdm",
    "tangent_lr",
)


def digest(values: Any) -> str:
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def identity() -> dict[str, Any]:
    return {
        **software_identity(),
        "decoding_libraries": {
            name: version(name) for name in ("scikit-learn", "pyriemann", "threadpoolctl")
        },
    }


def read_protocol(path: Path) -> tuple[dict[str, Any], str]:
    values = yaml.safe_load(path.read_text())
    if not isinstance(values, dict):
        raise ValueError("Decoding protocol must be a mapping")
    checksum = digest(values)
    if path.with_suffix(".sha256").read_text().strip() != checksum:
        raise ValueError("Decoding protocol seal mismatch")
    if path.name == "decoding.yaml":
        receipt = json.loads(path.with_name("decoding-freeze.json").read_text())
        document = Path(__file__).resolve().parents[3] / "docs/DECODING_PROTOCOL.md"
        if (
            receipt["protocol_sha256"] != checksum
            or receipt["document_sha256"] != sha256(document)
            or receipt["configuration_file_sha256"] != sha256(path)
        ):
            raise ValueError("Decoding protocol freeze receipt mismatch")
    protocol = values.get("protocol", values)
    if tuple(protocol["models"]) != MODELS:
        raise ValueError("Use all nine prespecified models in their declared order")
    if set(protocol["development_subjects"]) & set(protocol["heldout_subjects"]):
        raise ValueError("Development and held-out subjects must be disjoint")
    if protocol["runs"] != [4, 8, 12] or len(set(protocol["channels"])) != len(
        protocol["channels"]
    ):
        raise ValueError("Invalid run/channel policy")
    if (
        protocol["epoch"] != [1.0, 3.0]
        or protocol["context"] != [0.0, 4.0]
        or protocol["fs_hz"] != 160.0
    ):
        raise ValueError("The sealed decoding window/context/sampling policy is fixed")
    if "protocol" in values:
        required = {
            "initial_protocol_sha256",
            "selected_parameters",
            "software",
            "verification_sha256",
            "development_dataset_fingerprint",
            "frozen_at_utc",
            "heldout_accessed",
        }
        if not required <= set(values):
            raise ValueError("Frozen configuration is missing provenance/selection rules")
        if values.get("initial_protocol_sha256") != digest(protocol) or set(
            values.get("selected_parameters", {})
        ) != set(MODELS):
            raise ValueError(
                "Frozen selection rules must retain the initial protocol and all models"
            )
        from soma.decoding.models import parameter_grid

        for model, params in values["selected_parameters"].items():
            if params not in parameter_grid(model, protocol, True):
                raise ValueError("Frozen hyperparameters are outside the prespecified grid")
    return values, checksum
