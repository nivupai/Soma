"""Purpose-scoped research-use assertions, distinct from legal or consent authorization."""

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from soma.human.evidence import EvidenceBundle

from soma.human.model import checksum, now, timestamp
from soma.protocol.model import ProtocolError, closed
from soma.results.contracts import canonical

ACTIONS = {"metadata", "analyze", "export_aggregate", "export_records", "redistribute"}


@dataclass(frozen=True)
class PermissionEvidence:
    _canonical: bytes

    def __post_init__(self) -> None:
        if (
            len(self._canonical) > 1024**2
            or canonical(json.loads(self._canonical)) != self._canonical
        ):
            raise ProtocolError("Immutable evidence requires bounded canonical serialization")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PermissionEvidence":
        closed(
            value,
            {
                "schema",
                "dataset",
                "version",
                "agreement_id",
                "agreement_version",
                "source",
                "source_sha256",
                "authority",
                "access_source",
                "license",
                "purposes",
                "actions",
                "restrictions",
                "review_status",
                "reviewed_at",
                "expires_at",
                "consent_status",
            },
        )
        if value["schema"] != "soma.human.permission/1.0.0":
            raise ProtocolError("Unsupported permission schema")
        if value["authority"] not in {"PUBLIC_NOTICE", "LOCAL_REVIEW", "UNKNOWN"}:
            raise ProtocolError("Unknown authority")
        if value["review_status"] not in {"SUPPORTED", "UNKNOWN", "REVOKED", "CONFLICT"}:
            raise ProtocolError("Unknown review status")
        if set(value["actions"]) - ACTIONS:
            raise ProtocolError("Unknown use action")
        if not isinstance(value["restrictions"], list) or not isinstance(value["purposes"], list):
            raise ProtocolError("Explicit purpose/restrictions required")
        from urllib.parse import urlsplit

        from soma.human.model import token
        from soma.workflow.privacy import redact_export

        token(value["dataset"])
        token(value["version"])
        for field in ["source", "agreement_id"]:
            text = value[field]
            if isinstance(text, str) and text.startswith("https://"):
                url = urlsplit(text)
                if not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ProtocolError("Credential-free public evidence URLs required")
            else:
                token(text)
        for field in ["purposes", "actions", "restrictions"]:
            if not all(isinstance(x, str) and x for x in value[field]):
                raise ProtocolError("Explicit textual purposes/actions/restrictions required")
        if redact_export(value) != value:
            raise ProtocolError("Private locations do not belong in portable permission evidence")
        checksum(value["source_sha256"])
        timestamp(value["reviewed_at"])
        if value["expires_at"] is not None:
            timestamp(value["expires_at"])
        if value["consent_status"] != "NOT_VERIFIED":
            raise ProtocolError("A license does not verify individual consent")
        return cls(canonical(value))

    def document(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        PermissionEvidence.from_dict(value)
        return dict(value)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._canonical).hexdigest()


def evidence(
    dataset: str,
    version: str,
    content: bytes,
    *,
    source: str,
    license: str,
    supported: bool = False,
) -> PermissionEvidence:
    return PermissionEvidence.from_dict(
        {
            "schema": "soma.human.permission/1.0.0",
            "dataset": dataset,
            "version": version,
            "agreement_id": source,
            "agreement_version": None,
            "source": source,
            "source_sha256": hashlib.sha256(content).hexdigest(),
            "authority": "PUBLIC_NOTICE" if supported else "UNKNOWN",
            "access_source": "LOCAL_OPERATOR_SELECTED_CACHE",
            "license": license,
            "purposes": ["methods_research"] if supported else [],
            "actions": ["metadata", "analyze", "export_aggregate"] if supported else ["metadata"],
            "restrictions": [
                "no raw data or participant records in portable exports",
                "attribution required where requested; no consent attestation",
            ],
            "review_status": "SUPPORTED" if supported else "UNKNOWN",
            "reviewed_at": now(),
            "expires_at": None,
            "consent_status": "NOT_VERIFIED",
        }
    )


def check_permission(
    record: PermissionEvidence,
    *,
    dataset: str,
    version: str,
    purpose: str,
    action: str,
    source_content: bytes | None,
    at: str | None = None,
) -> dict[str, Any]:
    d = record.document()
    reasons = []
    if action not in ACTIONS:
        raise ProtocolError("Unknown permission action")
    if action in {"export_records", "redistribute"}:
        reasons.append(
            "Raw/participant-record export is not implemented or authorized by this policy"
        )
    if (d["dataset"], d["version"]) != (dataset, version):
        reasons.append("dataset/version mismatch")
    if source_content is None or hashlib.sha256(source_content).hexdigest() != d["source_sha256"]:
        reasons.append("permission source missing or changed")
    if d["review_status"] != "SUPPORTED":
        reasons.append("unknown, conflicting or revoked permission")
    if d["expires_at"] and timestamp(at or now()) >= timestamp(d["expires_at"]):
        reasons.append("authorization expired")
    if timestamp(d["reviewed_at"]) > timestamp(at or now()):
        reasons.append("review timestamp is in the future")
    if purpose not in d["purposes"] or action not in d["actions"]:
        reasons.append("purpose/action not supported")
    if d["authority"] == "PUBLIC_NOTICE" and source_content is not None:
        text = source_content.decode(errors="replace")
        recognized = (
            dataset == "eegmmidb"
            and d["license"] == "ODC-By-1.0"
            and "EEG Motor Movement/Imagery" in text
            and "Open Data Commons Attribution License v1.0" in text
            and d["source"] == "https://physionet.org/content/eegmmidb/1.0.0/"
        ) or (
            dataset == "ibsr-v2"
            and d["license"] == "LOCAL-ROHLFING-NOTICE"
            and "Rohlfing" in text
            and "public domain" in text
        )
        if dataset == "ds000114" and d["license"] == "CC0":
            try:
                description = json.loads(text)
                recognized = (
                    description.get("License") == "CC0"
                    and description.get("DatasetDOI") == "doi:10.18112/openneuro.ds000114.v1.0.2"
                )
            except ValueError:
                recognized = False
        if dataset == "bnci2014-001" and d["license"] == "CC-BY-ND-4.0":
            section = text.partition("Four class motor imagery (001-2014)")[2].partition(
                "Two class motor imagery (002-2014)"
            )[0]
            recognized = (
                d["source"] == "https://bnci-horizon-2020.eu/database/data-sets"
                and "Four class motor imagery (001-2014)" in text
                and "CC BY-ND 4.0" in section
            )
            if action == "export_aggregate":
                reasons.append("ND aggregate export requires separate content-bound local review")
        if not recognized:
            reasons.append("license claim inconsistent with recognized source")
    if d["authority"] == "UNKNOWN":
        reasons.append("no reviewed authorization source")
    return {
        "allowed": not reasons,
        "status": "SUPPORTED_FOR_SOFTWARE_POLICY" if not reasons else "REQUIRES_AUTHORIZATION",
        "reasons": reasons,
        "evidence_fingerprint": record.fingerprint,
        "legal_authorization_established": False,
        "consent_verified": False,
    }


def permission_readiness(
    record: PermissionEvidence,
    source_content: bytes | None,
    bundle: "EvidenceBundle",
    references: dict[str, tuple["Path", str]],
    *,
    purpose: str = "methods_research",
    action: str = "analyze",
    at: str | None = None,
) -> dict[str, Any]:
    """Existing policy plus content-bound review; neither establishes legal consent."""
    from soma.human.evidence import verify_bundle

    d, b = record.document(), bundle.document()
    policy = check_permission(
        record,
        dataset=b["dataset"],
        version=b["version"],
        purpose=purpose,
        action=action,
        source_content=source_content,
        at=at,
    )
    integrity = verify_bundle(bundle, references, at=at)
    entries = [e for e in b["entries"] if e["kind"] in {"license", "agreement", "irb", "consent"}]
    reasons = list(policy["reasons"])
    if not any(e["sha256"] == d["source_sha256"] for e in entries):
        reasons.append("permission source is not bound to reviewed bundle")
    for e in entries:
        if (
            e["sha256"] == d["source_sha256"]
            and d["agreement_version"] is not None
            and e["document_version"] != d["agreement_version"]
        ):
            reasons.append("agreement version does not match reviewed evidence")
        row = next(r for r in integrity["entries"] if r["id"] == e["id"])
        if row["status"] != "READY":
            reasons.extend(e["id"] + ": " + text for text in row["reasons"])
        if purpose != e["purpose"] or action not in e["actions"]:
            reasons.append("conflicting evidence purpose/action scope")
        if e["distribution"] == "UNKNOWN" or (
            action == "export_aggregate" and e["distribution"] != "AGGREGATE_ONLY"
        ):
            reasons.append("distribution scope unsupported")
    return {
        "schema": "soma.human.permission-readiness/1.0.0",
        "status": "READY" if not reasons else "BLOCKED",
        "reasons": sorted(set(reasons)),
        "policy": policy,
        "bundle_fingerprint": bundle.fingerprint,
        "legal_authorization_established": False,
        "consent_verified": False,
        "issuer_authentication": "LOCAL_REVIEW_ASSERTIONS_ONLY",
    }
