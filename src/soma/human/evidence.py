"""Content-addressed evidence references using existing canonical protocol contracts.

Integrity is not document authority, consent, or independent timestamp attestation.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.human.model import checksum, now, timestamp, token
from soma.protocol.model import ProtocolError, closed
from soma.results.contracts import canonical
from soma.workflow.privacy import redact_export

KINDS = {
    "registration",
    "agreement",
    "license",
    "consent",
    "irb",
    "identity",
    "preprocessing",
    "bids_validation",
    "transform",
    "qc",
    "protocol_seal",
    "snapshot",
}


def local_file(root: Path, relative: str) -> Path:
    """Explicit root-relative regular file, checked before reading any content."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ProtocolError("Explicit relative evidence path required")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ProtocolError("Evidence path traversal forbidden")
    base = root.resolve(strict=True)
    path = (base / rel).resolve(strict=True)
    if not path.is_relative_to(base) or not path.is_file():
        raise ProtocolError("Evidence outside permitted root")
    return path


@dataclass(frozen=True)
class EvidenceBundle:
    _canonical: bytes

    def __post_init__(self) -> None:
        if len(self._canonical) > 1024**2:
            raise ProtocolError("Evidence manifest exceeds bound")
        d = json.loads(self._canonical)
        if canonical(d) != self._canonical:
            raise ProtocolError("Canonical immutable evidence required")
        closed(d, {"schema", "dataset", "version", "protocol_fingerprint", "created_at", "entries"})
        if d["schema"] != "soma.evidence.bundle/1.0.0":
            raise ProtocolError("Unsupported evidence bundle schema")
        token(d["dataset"])
        token(d["version"])
        checksum(d["protocol_fingerprint"])
        timestamp(d["created_at"])
        if not isinstance(d["entries"], list) or not 1 <= len(d["entries"]) <= 128:
            raise ProtocolError("Explicit bounded evidence entries required")
        ids = set()
        for e in d["entries"]:
            closed(
                e,
                {
                    "id",
                    "kind",
                    "sha256",
                    "issuer",
                    "source",
                    "document_version",
                    "issued_at",
                    "valid_from",
                    "expires_at",
                    "revoked_at",
                    "review",
                    "purpose",
                    "actions",
                    "distribution",
                },
            )
            token(e["id"])
            token(e["issuer"])
            if e["document_version"] is not None:
                token(e["document_version"])
            if e["id"] in ids or e["kind"] not in KINDS:
                raise ProtocolError("Duplicate or unsupported evidence reference")
            ids.add(e["id"])
            checksum(e["sha256"])
            token(e["source"])
            token(e["purpose"])
            if not isinstance(e["actions"], list) or not e["actions"]:
                raise ProtocolError("Evidence purpose/action scope required")
            for action in e["actions"]:
                token(action)
            if e["distribution"] not in {"PRIVATE_ONLY", "AGGREGATE_ONLY", "UNKNOWN"}:
                raise ProtocolError("Explicit distribution limits required")
            for field in ["issued_at", "valid_from", "expires_at", "revoked_at"]:
                if e[field] is not None:
                    timestamp(e[field])
            if (
                e["expires_at"]
                and e["valid_from"]
                and timestamp(e["expires_at"]) <= timestamp(e["valid_from"])
            ):
                raise ProtocolError("Invalid evidence validity interval")
            closed(e["review"], {"status", "reviewer", "reviewed_at"})
            r = e["review"]
            if r["status"] not in {"APPROVED", "REQUIRED", "REJECTED", "CONFLICT"}:
                raise ProtocolError("Unknown human review state")
            if r["status"] == "APPROVED" and (r["reviewer"] is None or r["reviewed_at"] is None):
                raise ProtocolError("Approval requires explicit human review provenance")
            if r["reviewer"] is not None:
                token(r["reviewer"])
            if r["reviewed_at"] is not None:
                timestamp(r["reviewed_at"])
        if redact_export(d) != d:
            raise ProtocolError("Private paths/credentials do not belong in portable evidence")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceBundle":
        return cls(canonical(value))

    def document(self) -> dict[str, Any]:
        return dict(json.loads(self._canonical))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._canonical).hexdigest()


def seal_bundle(
    dataset: str,
    version: str,
    protocol_fingerprint: str,
    entries: list[dict[str, Any]],
    *,
    created_at: str | None = None,
) -> EvidenceBundle:
    return EvidenceBundle.from_dict(
        {
            "schema": "soma.evidence.bundle/1.0.0",
            "dataset": dataset,
            "version": version,
            "protocol_fingerprint": protocol_fingerprint,
            "created_at": created_at or now(),
            "entries": entries,
        }
    )


def write_bundle(bundle: EvidenceBundle, path: Path) -> None:
    """Exclusive immutable local write; underlying private documents are never copied."""
    from soma.workflow.runtime import safe_root

    safe_root(path.parent, create=True)
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(canonical({"bundle": bundle.document(), "sha256": bundle.fingerprint}) + b"\n")


def read_bundle(path: Path) -> EvidenceBundle:
    from soma.results.io import read_json

    d = read_json(path)
    closed(d, {"bundle", "sha256"})
    bundle = EvidenceBundle.from_dict(d["bundle"])
    if d["sha256"] != bundle.fingerprint:
        raise ProtocolError("Tampered evidence bundle seal")
    return bundle


def verify_bundle(
    bundle: EvidenceBundle, references: dict[str, tuple[Path, str]], *, at: str | None = None
) -> dict[str, Any]:
    """References are private root/path pairs, never embedded in the portable manifest."""
    rows = []
    current = timestamp(at or now())
    if timestamp(bundle.document()["created_at"]) > current:
        raise ProtocolError("Future evidence seal timestamp")
    if set(references) - {e["id"] for e in bundle.document()["entries"]}:
        raise ProtocolError("Unbound evidence reference")
    for e in bundle.document()["entries"]:
        reasons = []
        intact = False
        if e["id"] in references:
            root, relative = references[e["id"]]
            try:
                path = local_file(root, relative)
                if path.stat().st_size > 64 * 1024**2:
                    raise ProtocolError("Evidence document exceeds64MiB bound")
                intact = sha256(path) == e["sha256"]
                if not intact:
                    reasons.append("content hash mismatch")
            except (OSError, ValueError):
                reasons.append("missing or unsafe evidence reference")
        else:
            reasons.append("underlying evidence not available")
        if e["revoked_at"] and timestamp(e["revoked_at"]) <= current:
            reasons.append("evidence revoked")
        if e["expires_at"] and current >= timestamp(e["expires_at"]):
            reasons.append("evidence expired")
        if e["valid_from"] and current < timestamp(e["valid_from"]):
            reasons.append("evidence not yet valid")
        if e["issued_at"] and current < timestamp(e["issued_at"]):
            reasons.append("future issuer timestamp")
        r = e["review"]
        if r["status"] != "APPROVED":
            reasons.append("human review " + r["status"].lower())
        if r["reviewed_at"] and current < timestamp(r["reviewed_at"]):
            reasons.append("future human review timestamp")
        rows.append(
            {
                "id": e["id"],
                "kind": e["kind"],
                "integrity": "PASS" if intact else "FAIL",
                "status": "READY" if not reasons else "BLOCKED",
                "reasons": reasons,
            }
        )
    return {
        "schema": "soma.evidence.integrity/1.0.0",
        "bundle_fingerprint": bundle.fingerprint,
        "status": "READY" if all(r["status"] == "READY" for r in rows) else "BLOCKED",
        "entries": rows,
        "document_authority_verified": False,
        "legal_authorization_established": False,
        "consent_verified": False,
    }
