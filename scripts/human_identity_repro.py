"""Deterministic fictional identity/evidence report; never requires human datasets in CI."""

import argparse
import hashlib
import json
import platform

from soma.human.adapters import identity
from soma.human.permissions import PermissionEvidence, check_permission, evidence
from soma.human.registration import inspect_registration
from soma.human.workflow import freeze_cohort, template
from soma.workflow.examples import example
from soma.workflow.model import digest


def report():
    key = bytes(range(32))
    content = b"Synthetic CI fixture: Torsten Rohlfing public domain notice"
    first = identity(
        "ibsr-v2",
        "fixture",
        "fictional-person",
        key,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(content).hexdigest()],
    )
    other = identity(
        "another-fictional-dataset",
        "fixture",
        "fictional-person",
        key,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(content).hexdigest()],
    )
    assert first.document()["subject"] != other.document()["subject"]
    e = evidence(
        "ibsr-v2",
        "fixture",
        content,
        source="synthetic-ci-notice",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    ).document()
    e["reviewed_at"] = "2020-01-01T00:00:00+00:00"
    permission = PermissionEvidence.from_dict(e)
    check = check_permission(
        permission,
        dataset="ibsr-v2",
        version="fixture",
        purpose="methods_research",
        action="analyze",
        source_content=content,
        at="2026-01-01T00:00:00+00:00",
    )
    assert check["allowed"] and not check["consent_verified"]
    protocol = freeze_cohort(template("ibsr-v2", "fixture"), [first]).protocol
    registration = inspect_registration({}, protocol)
    assert registration["status"] == "UNVERIFIED"
    invariants = {
        "identity_fingerprint": first.fingerprint,
        "canonical_identity": first._canonical.decode(),
        "permission_fingerprint": permission.fingerprint,
        "permission_check": check,
        "protocol_fingerprint": protocol.fingerprint,
        "registration_schema": registration["schema"],
        "registration_status": registration["status"],
        "synthetic_lineage": digest(example("source").to_dict()),
        "actual_human_data_accessed": False,
    }
    return {
        "schema": "soma.human.synthetic-repro/1.0.0",
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "invariants": invariants,
        "all_passed": True,
    }


if __name__ == "__main__":
    from pathlib import Path

    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report(), indent=2) + "\n")
