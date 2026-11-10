"""Evidence integrity, scope and review are tested independently of legal consent."""

import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from soma.human.evidence import (
    EvidenceBundle,
    local_file,
    read_bundle,
    seal_bundle,
    verify_bundle,
    write_bundle,
)
from soma.human.permissions import evidence, permission_readiness
from soma.protocol.model import ProtocolError

CONTENT = b"Synthetic fixture: Torsten Rohlfing public domain notice"


def entry(content=CONTENT, kind="license", id="notice"):
    return {
        "id": id,
        "kind": kind,
        "sha256": hashlib.sha256(content).hexdigest(),
        "issuer": "fictional-issuer",
        "source": "fictional-source",
        "document_version": "1",
        "issued_at": "2020-01-01T00:00:00Z",
        "valid_from": "2020-01-01T00:00:00Z",
        "expires_at": None,
        "revoked_at": None,
        "review": {
            "status": "APPROVED",
            "reviewer": "fictional-reviewer",
            "reviewed_at": "2020-01-02T00:00:00Z",
        },
        "purpose": "methods_research",
        "actions": ["analyze", "export_aggregate"],
        "distribution": "AGGREGATE_ONLY",
    }


def setup(tmp_path, entries=None):
    p = tmp_path / "notice.txt"
    p.write_bytes(CONTENT)
    b = seal_bundle(
        "ibsr-v2",
        "fixture",
        hashlib.sha256(b"protocol").hexdigest(),
        entries or [entry()],
        created_at="2020-01-03T00:00:00Z",
    )
    return b, {"notice": (tmp_path, p.name)}


def test_seal_is_immutable_copied_and_exclusive(tmp_path):
    b, refs = setup(tmp_path)
    d = b.document()
    d["entries"][0]["issuer"] = "changed"
    assert b.document()["entries"][0]["issuer"] == "fictional-issuer"
    with pytest.raises(FrozenInstanceError):
        b._canonical = b"{}"
    p = tmp_path / "bundle.local.json"
    write_bundle(b, p)
    assert read_bundle(p).fingerprint == b.fingerprint
    with pytest.raises(FileExistsError):
        write_bundle(b, p)
    assert verify_bundle(b, refs)["status"] == "READY"
    v = json.loads(p.read_text())
    v["bundle"]["entries"][0]["issuer"] = "changed"
    p.write_text(json.dumps(v))
    with pytest.raises(ProtocolError, match="Tampered"):
        read_bundle(p)


@pytest.mark.parametrize(
    "fault",
    ["hash", "expired", "revoked", "notyet", "review", "future-review", "conflict", "missing"],
)
def test_evidence_failure_is_not_approval(tmp_path, fault):
    e = entry()
    if fault == "hash":
        e["sha256"] = hashlib.sha256(b"changed").hexdigest()
    elif fault == "expired":
        e["expires_at"] = "2021-01-01T00:00:00Z"
    elif fault == "revoked":
        e["revoked_at"] = "2021-01-01T00:00:00Z"
    elif fault == "notyet":
        e["valid_from"] = "2090-01-01T00:00:00Z"
    elif fault == "review":
        e["review"]["status"] = "REQUIRED"
    elif fault == "future-review":
        e["review"]["reviewed_at"] = "2090-01-01T00:00:00Z"
    elif fault == "conflict":
        e["review"]["status"] = "CONFLICT"
    b, refs = setup(tmp_path, [e])
    result = verify_bundle(b, {} if fault == "missing" else refs)
    assert result["status"] == "BLOCKED" and not result["consent_verified"]


@pytest.mark.parametrize("relative", ["../outside", "/private/outside", "..\\outside", ""])
def test_paths_rejected_before_read(tmp_path, relative):
    with pytest.raises((ValueError, OSError)):
        local_file(tmp_path, relative)


def test_symlink_escape_denied(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "private"
    outside.write_bytes(CONTENT)
    (root / "link").symlink_to(outside)
    with pytest.raises(ProtocolError):
        local_file(root, "link")


def test_permission_requires_bound_review_and_conflict_veto(tmp_path):
    permission = evidence(
        "ibsr-v2",
        "fixture",
        CONTENT,
        source="fictional-source",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    )
    b, refs = setup(tmp_path)
    r = permission_readiness(permission, CONTENT, b, refs)
    assert r["status"] == "READY" and not r["legal_authorization_established"]
    e = entry(id="second")
    e["actions"] = ["metadata"]
    b, _ = setup(tmp_path, [entry(), e])
    refs["second"] = refs["notice"]
    assert permission_readiness(permission, CONTENT, b, refs)["status"] == "BLOCKED"
    assert (
        permission_readiness(permission, CONTENT, b, refs, action="export_records")["status"]
        == "BLOCKED"
    )


@pytest.mark.parametrize(
    "fault",
    ["schema", "unknown", "duplicate", "approval", "interval", "private-source", "private-issuer"],
)
def test_bad_manifest_rejected(tmp_path, fault):
    b, _ = setup(tmp_path)
    d = b.document()
    if fault == "schema":
        d["schema"] = "unsupported"
    elif fault == "unknown":
        d["unexpected"] = True
    elif fault == "duplicate":
        d["entries"] *= 2
    elif fault == "approval":
        d["entries"][0]["review"]["reviewer"] = None
    elif fault == "interval":
        d["entries"][0]["expires_at"] = "2019-01-01T00:00:00Z"
    elif fault == "private-source":
        d["entries"][0]["source"] = "../private-document"
    else:
        d["entries"][0]["issuer"] = "https://user:password@private.invalid"
    with pytest.raises((ValueError, TypeError)):
        EvidenceBundle.from_dict(d)


def test_agreement_version_discrepancy_blocks_even_with_same_content(tmp_path):
    from soma.human.permissions import PermissionEvidence

    b, refs = setup(tmp_path)
    p = evidence(
        "ibsr-v2",
        "fixture",
        CONTENT,
        source="fictional-source",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    ).document()
    p["agreement_version"] = "2"
    result = permission_readiness(PermissionEvidence.from_dict(p), CONTENT, b, refs)
    assert result["status"] == "BLOCKED" and any("version" in r for r in result["reasons"])
