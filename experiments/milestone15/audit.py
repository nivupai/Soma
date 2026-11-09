"""Preservation, scientific-contract and release-privacy receipt (aggregate only)."""

import hashlib
import json
import re
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any

from services.explorer_api.app import create_app
from soma.pipeline.cache import source_hash


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ledger = json.loads(Path("data/derived/milestone15/baseline-ledger.json").read_text())
    groups = {"tests": 0, "reports": 0}
    for name, expected in ledger.items():
        assert sha(Path(name)) == expected, name
        groups["tests" if name.startswith("tests/") else "reports"] += 1
    checks: dict[str, Any] = {}
    for name, required in [
        ("full-tests", "892 passed"),
        ("offline-tests", "875 passed"),
        ("ui-tests", "14 passed"),
        ("e2e", "8 passed"),
        ("ruff", "All checks passed"),
        ("python-format", "files already formatted"),
        ("mypy", "Success: no issues found"),
        ("dependencies", "No broken requirements"),
        ("format", "All matched files use Prettier"),
    ]:
        text = Path(f"/private/tmp/soma15-{name}.log").read_text()
        assert required in text, name
        checks[name] = [line.strip("= ") for line in text.splitlines() if required in line][-1]
    for name in ["ts", "frontend-lint"]:
        text = Path(f"/private/tmp/soma15-{name}.log").read_text()
        assert not re.search(r"error TS|[1-9]\d* problems|[1-9]\d* errors", text), name
        checks[name] = "passed"
    assert version("soma-neuro") == "0.15.0"
    previous = subprocess.check_output(
        ["git", "diff", "--name-only", "294f794", "--", "src/soma"], text=True
    ).splitlines()
    assert previous == ["src/soma/__init__.py"], previous
    shots = {str(p): sha(p) for p in sorted(Path("docs/assets/explorer").glob("*.png"))}
    assert len(shots) == 6
    openapi = create_app().openapi()
    assert "SourceSeries" in openapi["components"]["schemas"]
    assert "state" in openapi["components"]["schemas"]["Artifact"]["properties"]
    Path("docs/explorer-openapi.json").write_text(json.dumps(openapi, indent=2) + "\n")
    api = json.loads(Path("experiments/milestone15/api-performance.json").read_text())
    browser = json.loads(Path("experiments/milestone15/browser-performance.json").read_text())
    assert "mesh_template_artifact" in api["measurements"]
    code_files = [
        *Path("services").rglob("*.py"),
        *Path("apps/explorer/src").rglob("*.ts"),
        *Path("apps/explorer/src").rglob("*.tsx"),
        *Path("apps/explorer/src").rglob("*.css"),
    ]
    receipt = {
        "version": "0.15.0",
        "baseline": "294f794",
        "baseline_tests": 851,
        "full_tests": 892,
        "new_API_tests": 41,
        "offline_tests": 875,
        "offline_deselected": 17,
        "frontend_tests": 14,
        "E2E_tests": 8,
        "local_E2E_skipped": False,
        "preserved_files_verified": groups,
        "checks": checks,
        "soma_source_sha256": source_hash(),
        "explorer_code_sha256": {str(p): sha(p) for p in sorted(code_files)},
        "frontend_lock_sha256": sha(Path("apps/explorer/package-lock.json")),
        "schema_sha256": sha(Path("docs/explorer-openapi.json")),
        "synthetic_screenshots_sha256": shots,
        "API_route_count": len(openapi["paths"]),
        "local_coverage": {
            "cached_EEG_recordings": 1,
            "cached_T1w": 1,
            "sealed_template_source_bundle": 1,
            "historical_synthetic_fmri_effect": 1,
            "human_preprocessing": 0,
            "human_retest": 0,
        },
        "API_performance_sha256": sha(Path("experiments/milestone15/api-performance.json")),
        "browser_performance_sha256": sha(Path("experiments/milestone15/browser-performance.json")),
        "peak_API_process_RSS_MiB": api["process_peak_RSS_MiB"],
        "browser_heap_used_bytes": browser["JS_heap_used_bytes"],
        "privacy": "Aggregate evidence and synthetic screenshots; participant files excluded",
        "limitations": [
            "No validated human fMRIPrep/retest",
            "Descriptive inference only",
            "Curated adapters, not arbitrary format import",
            "Reduced source-space display mesh, not BEM",
            "No automatic expensive experiment execution",
            "Cooperative job cancellation",
        ],
    }
    Path("experiments/milestone15/verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "preserved": groups,
                "API_paths": len(openapi["paths"]),
                "synthetic_screenshots": len(shots),
            }
        )
    )


if __name__ == "__main__":
    main()
