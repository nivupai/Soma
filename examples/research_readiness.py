"""Fictional metadata only: no files, human data, provider retrieval or study registration."""

import hashlib

from soma.human.adapters import identity
from soma.human.model import Identity
from soma.human.workflow import template
from soma.results.contracts import canonical
from soma.sdk.readiness import Gate, aggregate, seal_bundle, session_audit, verify_attachment


def run():
    p = template("ibsr-v2", "fictional")
    content = b"fictional evidence; not a human agreement"
    entry = {
        "id": "fictional-notice",
        "kind": "license",
        "sha256": hashlib.sha256(content).hexdigest(),
        "issuer": "fictional-issuer",
        "source": "fictional-source",
        "document_version": "1",
        "issued_at": "2020-01-01T00:00:00Z",
        "valid_from": None,
        "expires_at": None,
        "revoked_at": None,
        "review": {"status": "REQUIRED", "reviewer": None, "reviewed_at": None},
        "purpose": "methods_research",
        "actions": ["metadata"],
        "distribution": "UNKNOWN",
    }
    b = seal_bundle(
        "ibsr-v2", "fictional", p.fingerprint, [entry], created_at="2020-01-02T00:00:00Z"
    )
    first = identity(
        "fictional",
        "1",
        "person",
        bytes(range(32)),
        modality="fMRI",
        task="motor",
        session="a",
        hashes=[hashlib.sha256(content).hexdigest()],
        acquisition={"task_definition": "fictional"},
        temporal={"tr_s": 2},
        spatial={"frame": "fictional-common"},
    )
    d = first.document()
    d["session"] = "b"
    second = Identity.from_dict(d)
    sessions = session_audit([first, second], chronology_required=True)
    registration = verify_attachment(p, "abc12", "1" * 24, "1", canonical(p.document()))
    assert registration["status"] == "UNVERIFIED"
    assert aggregate([Gate("ready", "READY", ()), Gate("required", "BLOCKED", ())]) == "BLOCKED"
    return {
        "synthetic_only": True,
        "bundle_fingerprint": b.fingerprint,
        "canonical_bundle": b._canonical.decode(),
        "session_relationship": sessions["relationship"],
        "session_status": sessions["status"],
        "independent_participants": sessions["independent_participants"],
        "registration_schema": registration["schema"],
        "registration_status": registration["status"],
        "blocked_gate_override_prevented": True,
        "actual_external_attestation": False,
        "actual_human_data_accessed": False,
    }


if __name__ == "__main__":
    print(run())
