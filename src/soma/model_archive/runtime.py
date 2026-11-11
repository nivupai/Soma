"""Explicit local EEGBCI request; no evaluation-role data or implicit download."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from soma.eeg_benchmark.data import load_dataset
from soma.human.permissions import PermissionEvidence, check_permission
from soma.model_archive.archive import numerical_receipt
from soma.model_archive.protocol import inspect_training
from soma.model_archive.training import archive_models, source_inventory
from soma.protocol.model import read_seal
from soma.results.io import read_json


def train_source(request: dict[str, Any]) -> dict[str, Any]:
    root, out, cache = (Path(request[k]) for k in ["root", "output", "cache"])
    from soma.eeg_benchmark.runner import safe_locations

    safe_locations(root, out, cache)
    permission = PermissionEvidence.from_dict(read_json(Path(request["permission_file"])))
    notice = Path(request["permission_source"])
    if not check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="analyze",
        source_content=notice.read_bytes(),
    )["allowed"]:
        raise ValueError("Source-analysis permission policy does not support fitting")
    key_doc = read_json(Path(request["key_file"]))
    key = bytes.fromhex(key_doc["key_hex"])
    inv = source_inventory(root, key)
    sealed = read_seal(Path(request["seal"]))
    v = inspect_training(sealed)
    if (
        v["dataset"] != "eegmmidb"
        or inv["fingerprint"]
        != sealed.protocol.document()["optional_metadata"]["inventory_fingerprint"]
    ):
        raise ValueError("Source inventory/protocol mismatch")
    out.parent.mkdir(parents=True, exist_ok=True)
    data, coverage = load_dataset(
        root,
        inv,
        v["configuration"],
        permission,
        notice,
        cache,
        coverage_path=out.parent / "coverage.local.json",
    )
    data = replace(data, provenance={**data.provenance, "dataset": "eegmmidb"})
    manifest = archive_models(data, sealed, out, permission=permission, notice=notice.read_bytes())
    numerical_receipt(
        {"inventory": inv, "coverage": coverage},
        {},
        out / "input-evidence",
        "soma.model-input-evidence",
    )
    return {
        "status": "NEW_MODEL_RELEASE_ARCHIVED",
        "id": manifest["id"],
        "cohort": manifest["cohort"],
        "historical_m22": False,
        "weights_private": True,
        "external_evaluation": "BLOCKED",
    }
