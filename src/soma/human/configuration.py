"""Explicit local request loading. No network fetch, imports, uploads or shell dispatch."""

from pathlib import Path
from typing import Any

from soma.human.adapters import Selection, bids_fmri, eeg, mri
from soma.human.permissions import PermissionEvidence
from soma.protocol.model import SealedProtocol, closed, read_seal
from soma.results.io import read_json


def request(path: Path) -> tuple[SealedProtocol, list[Selection], PermissionEvidence, Path]:
    d = read_json(path)
    closed(
        d,
        {
            "dataset",
            "root",
            "subjects",
            "runs",
            "key_file",
            "permission_file",
            "permission_source",
            "seal_file",
        },
    )
    if not isinstance(d["subjects"], list) or not 1 <= len(d["subjects"]) <= 128:
        raise ValueError("Explicit bounded subjects required")
    if not all(type(subject) is str and subject for subject in d["subjects"]):
        raise ValueError("Subject selectors must be explicit strings, never coerced booleans")
    if not isinstance(d["runs"], list) or any(type(v) not in (str, int) for v in d["runs"]):
        raise ValueError("Explicit run selectors required; booleans are not recording IDs")
    if d["dataset"] != "eegmmidb" and d["runs"]:
        raise ValueError("This anatomical/BIDS adapter has no explicit run-selection configuration")
    key = bytes.fromhex(read_json(Path(d["key_file"]))["key_hex"])
    root = Path(d["root"])
    selections: list[Selection] = []
    for subject in d["subjects"]:
        if d["dataset"] == "eegmmidb":
            if not d["runs"]:
                raise ValueError("Explicit EEG runs required")
            selections.extend(eeg(root, int(subject), int(run), key) for run in d["runs"])
        elif d["dataset"] in {"ibsr-v2", "mrbrains13"}:
            selections.append(mri(root, d["dataset"], subject, key))
        elif d["dataset"] == "ds000114":
            selections.extend(bids_fmri(root, subject, key))
        else:
            raise ValueError("Dataset has no human pilot adapter")
    return (
        read_seal(Path(d["seal_file"])),
        selections,
        PermissionEvidence.from_dict(read_json(Path(d["permission_file"]))),
        Path(d["permission_source"]),
    )


def export_audit(
    record: dict[str, Any], permission: PermissionEvidence, source: bytes
) -> dict[str, Any]:
    from soma.human.permissions import check_permission

    p = record["protocol"]["protocol"]["scientific"]["population"]
    dataset = record["units"][0]["identity"]["dataset"]
    version = record["units"][0]["identity"]["version"]
    check = check_permission(
        permission,
        dataset=dataset,
        version=version,
        purpose="methods_research",
        action="export_aggregate",
        source_content=source,
    )
    if not check["allowed"]:
        raise ValueError("Aggregate export is not supported by use evidence")
    return {
        "dataset": p["dataset_namespace"],
        "selected_records": len(record["units"]),
        "complete_records": sum(u["status"] == "COMPLETE" for u in record["units"]),
        "status": record["status"],
        "interpretation": "DESCRIPTIVE_ONLY",
        "participant_data_exported": False,
        "permission_check_is_legal_authorization": False,
    }
