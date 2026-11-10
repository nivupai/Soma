"""Read-only historical evidence adapter; no retrospective scientific completion."""

import hashlib
from pathlib import Path
from typing import Any

from soma.protocol.model import ProtocolError
from soma.results.io import read_json
from soma.workflow.runtime import permitted


def historical_evidence(root: Path, receipt: str) -> dict[str, Any]:
    path = permitted(root, receipt)
    if not receipt.startswith(("configs/", "experiments/")) or path.suffix != ".json":
        raise ProtocolError("Select an explicit metadata freeze receipt, never participant data")
    value = read_json(path)
    checks = []
    for name, expected in value.get("files_sha256", {}).items():
        if not name.startswith(("configs/", "docs/", "experiments/")) or Path(name).suffix not in {
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".sha256",
        }:
            raise ProtocolError("Historical receipt does not authorize arbitrary data reads")
        try:
            resource = permitted(root, name)
            if resource.stat().st_size > 2 * 1024**2:
                raise ProtocolError("Historical metadata exceeds bound")
            actual = hashlib.sha256(resource.read_bytes()).hexdigest()
            status = "MATCH" if actual == expected else "MISMATCH"
        except (ValueError, OSError):
            actual = None
            status = "UNAVAILABLE"
        checks.append(
            {
                "reference": name,
                "recorded_sha256": expected,
                "observed_sha256": actual,
                "status": status,
            }
        )
    return {
        "schema": "soma.protocol.historical-evidence/1.0.0",
        "status": "INDETERMINATE",
        "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "recorded_declarations": value,
        "checks": checks,
        "missing": [
            "complete typed study/execution mapping",
            "independently verified registration/timing",
        ],
        "interpretation": (
            "original local declarations only; no new prospective or confirmatory status"
        ),
        "historical_source_modified": False,
    }
