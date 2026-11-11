"""Controlled explicit-root execution; blocked studies never manufacture outcomes."""

import json
import time
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.datasets.human_mri import safe_local_output
from soma.eeg_benchmark.evaluation import environment_snapshot
from soma.external_eeg.contracts import candidate_audit, inspect_plan
from soma.external_eeg.data import authorize, bnci_record, combine, inventory
from soma.external_eeg.study import evaluate
from soma.human.evidence import EvidenceBundle
from soma.human.permissions import PermissionEvidence, permission_readiness
from soma.pipeline.cache import source_hash
from soma.protocol.model import SealedProtocol
from soma.results.contracts import create_result
from soma.results.io import inspect_result, save_result
from soma.workflow.model import digest
from soma.workflow.privacy import redact_export


def write_receipt(d: dict[str, Any], output: Path) -> None:
    e = create_result(
        "experiment.manifest",
        {
            "computation": "external-eeg-audit-or-evaluation",
            "inputs": {},
            "environment": environment_snapshot(),
            "assumptions": ["explicit permission and dataset scope"],
            "validation": {"scope": "integrity and declared numerical checks"},
            "limitations": [
                "No historical M22 fitted model artifact",
                "Not independent peer review",
            ],
        },
        values=d,
        provenance={},
        method={"id": "soma.external-eeg.report", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(e, {}, output)


def read_receipt(path: Path) -> dict[str, Any]:
    e = inspect_result(path)["envelope"]
    if e["method"] != {"id": "soma.external-eeg.report", "version": "1"} or e["payload"]["arrays"]:
        raise ValueError("Not an external aggregate receipt")
    d = dict(e["payload"]["values"])
    if (
        d.get("confirmatory_claim_allowed") is not False
        or d.get("independent_external_replication") is not False
    ):
        raise ValueError("Unsupported scientific inference claim")

    def private(v: Any) -> None:
        if isinstance(v, dict):
            if set(v) & {
                "subject",
                "trial_id",
                "subject_key",
                "participant_key",
                "predictions",
                "path",
                "root",
            }:
                raise ValueError("Private participant fields in aggregate")
            for x in v.values():
                private(x)
        elif isinstance(v, list):
            for x in v:
                private(x)

    private(d)
    if redact_export(d) != d:
        raise ValueError("Private location in aggregate")
    if d.get("status") == "BLOCKED" and d.get("performance"):
        raise ValueError("Blocked human evaluation cannot report accuracy")
    if d.get("p_value") is not None:
        raise ValueError("Unsupported human exchangeability/significance claim")
    if d.get("original_m22_model") is True:
        raise ValueError("Original M22 model fidelity not established")
    for row in d.get("performance", []):
        if row["complete_subjects"] + row["missing_subjects"] != row["planned_subjects"]:
            raise ValueError("Dropped planned subjects")
        ci = row.get("balanced_accuracy")
        if ci is not None and (
            ci.get("unit") != "subject"
            or not 0 <= ci["lower"] <= ci["upper"] <= 1
            or ci["n_subjects"] != row["complete_subjects"]
        ):
            raise ValueError("Invalid subject-level uncertainty")
    return d


def run(
    sealed: SealedProtocol,
    root: Path,
    output: Path,
    permission: PermissionEvidence | None,
    notice: bytes | None,
    *,
    expected_inventory: dict[str, Any],
    bundle: EvidenceBundle | None = None,
    references: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    p = inspect_plan(sealed)
    safe_local_output(output)
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Output must not modify raw data")
    inv = inventory(root)
    if (
        inv != expected_inventory
        or inv["fingerprint"]
        != sealed.protocol.document()["optional_metadata"]["inventory_fingerprint"]
    ):
        raise ValueError("Changed input inventory after seal")
    result = {
        **candidate_audit(),
        "mode": p["mode"],
        "split": p["split"],
        "protocol_fingerprint": sealed.protocol.fingerprint,
        "inventory_fingerprint": inv["fingerprint"],
        "code_sha256": source_hash(),
        "observed_files": inv["available"],
        "execution_identity": digest(
            {
                "protocol": sealed.protocol.fingerprint,
                "inventory": inv["fingerprint"],
                "environment": environment_snapshot(),
                "implementation": source_hash(),
            }
        ),
    }
    blockers = []
    if inv["available"] != 18:
        blockers.append("All18 scheduled MAT files are not present; no auto-download")
    if permission is None or notice is None:
        blockers.append("Current analyze and aggregate-export evidence unavailable")
    else:
        try:
            authorize(permission, notice, p["version"])
            authorize(permission, notice, p["version"], "export_aggregate")
        except ValueError as error:
            blockers.append(str(error))
    if bundle is None or references is None:
        blockers.append("M21 content-bound permission evidence bundle unavailable")
    else:
        document = bundle.document()
        if (document["dataset"], document["version"], document["protocol_fingerprint"]) != (
            p["dataset"],
            p["version"],
            sealed.protocol.fingerprint,
        ):
            blockers.append("Evidence bundle dataset/version/protocol mismatch")
        elif permission is not None and notice is not None:
            for action in ["analyze", "export_aggregate"]:
                readiness = permission_readiness(
                    permission, notice, bundle, references, action=action
                )
                if readiness["status"] != "READY":
                    blockers.extend(readiness["reasons"])
    if p["mode"] != "EXTERNAL_REFIT":
        blockers.append("Original M22 model state unavailable; no implicit replacement fit")
    if blockers:
        result["blockers"] = blockers
        write_receipt(result, output)
        return result
    assert permission is not None and notice is not None
    tick = time.perf_counter()
    datasets = []
    coverage = []
    private = output / "private"
    private.mkdir(parents=True, exist_ok=True)
    for item in inv["records"]:
        row = {**item, "status": "FAILED"}
        try:
            data, decisions = bnci_record(
                root / item["file"],
                item["subject"],
                item["session"],
                item["sha256"],
                permission,
                notice,
                p["version"],
            )
            row["decisions"] = decisions
            if data is not None:
                import numpy as np

                if all(
                    min(
                        np.bincount(
                            data.y[data.metadata.run.to_numpy() == run], minlength=2
                        ).tolist()
                    )
                    >= 2
                    for run in p["runs"]
                ):
                    datasets.append(data)
                    row["status"] = "PREPROCESSED"
                else:
                    row["reason"] = "Prespecified run/class-count QC"

        except (ValueError, OSError) as error:
            row["reason"] = str(error)
        coverage.append(row)
    (private / "coverage.local.json").write_text(json.dumps(coverage, indent=2))
    eligible = {
        s for s in p["subjects"] if sum(s in set(d.metadata.subject) for d in datasets) == 2
    }
    datasets = [d for d in datasets if set(d.metadata.subject) <= eligible]
    if not datasets:
        result["blockers"] = ["No eligible trials; coverage retained"]
        write_receipt(result, output / "summary")
        return result
    data = combine(datasets)
    report, pred = evaluate(data, p, private / "models", synthetic=False)
    pred.to_csv(private / "predictions.local.csv", index=False)
    report.update(
        schema="soma.external-eeg.execution/1",
        protocol_fingerprint=sealed.protocol.fingerprint,
        inventory_fingerprint=inv["fingerprint"],
        code_sha256=source_hash(),
        wall_seconds=time.perf_counter() - tick,
        observed_sessions=len(datasets),
        observed_trials=len(data.y),
        private_file_hashes={
            f.relative_to(private).as_posix(): sha256(f) for f in private.rglob("*") if f.is_file()
        },
    )
    # Private hashes are integrity receipts, never participant rows in portable summaries.
    write_receipt(report, output / "summary")
    return report


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = ["mode", "split", "protocol_fingerprint", "inventory_fingerprint", "code_sha256"]
    same = all(left.get(k) == right.get(k) for k in keys) and all(
        k in left and k in right for k in keys
    )
    return {
        "status": "SAME_DECLARED_DESIGN" if same else "NOT_COMPARABLE",
        "numeric_comparison_authorized": same
        and left.get("status") != "BLOCKED"
        and right.get("status") != "BLOCKED",
        "independent_external_replication": False,
        "cache_interchangeability": False,
    }
