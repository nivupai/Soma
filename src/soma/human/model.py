"""Immutable dataset-scoped identity and evidence; no filename chronology inference."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from soma.protocol.model import ProtocolError, closed
from soma.results.contracts import canonical


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ProtocolError("Explicit timezone evidence required")
    return result


def checksum(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ProtocolError("Full SHA256 evidence required")


def token(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
        raise ProtocolError("Explicit bounded opaque identity required")


def pseudonym(dataset: str, subject: str, key: bytes) -> str:
    token(dataset)
    token(subject)
    if len(key) < 32:
        raise ProtocolError("A private pseudonym key of at least 32 bytes is required")
    return (
        "subject-" + hmac.new(key, (dataset + "\0" + subject).encode(), hashlib.sha256).hexdigest()
    )


@dataclass(frozen=True)
class Identity:
    _canonical: bytes

    def __post_init__(self) -> None:
        if (
            len(self._canonical) > 1024**2
            or canonical(json.loads(self._canonical)) != self._canonical
        ):
            raise ProtocolError("Immutable evidence requires bounded canonical serialization")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Identity":
        closed(
            value,
            {
                "schema",
                "dataset",
                "version",
                "subject",
                "session",
                "task",
                "run",
                "acquisition",
                "modality",
                "partition",
                "acquisition_metadata",
                "spatial_reference",
                "temporal_reference",
                "evidence",
                "availability",
                "chronology",
                "consent_evidence",
            },
        )
        if value["schema"] != "soma.human.identity/1.0.0":
            raise ProtocolError("Unsupported human identity schema")
        for k in ["dataset", "version", "subject", "task", "partition"]:
            token(value[k])
        if not re.fullmatch(r"subject-[a-f0-9]{64}", value["subject"]):
            raise ProtocolError("Use a dataset-scoped keyed pseudonym")
        for k in ["session", "run", "acquisition"]:
            if value[k] is not None:
                token(value[k])
        if value["modality"] not in {"EEG", "MRI", "fMRI"} or value["availability"] not in {
            "AVAILABLE",
            "MISSING",
        }:
            raise ProtocolError("Explicit supported modality/availability required")
        if not value["evidence"]:
            raise ProtocolError("Identity evidence is mandatory")
        for e in value["evidence"]:
            checksum(e)
        if value["chronology"] is not None:
            closed(value["chronology"], {"acquired_at", "source_sha256"})
            timestamp(value["chronology"]["acquired_at"])
            checksum(value["chronology"]["source_sha256"])
            if value["chronology"]["source_sha256"] not in value["evidence"]:
                raise ProtocolError("Acquisition chronology lacks source correspondence")
        if value["consent_evidence"] != "NOT_PROVIDED":
            raise ProtocolError("No consent verification adapter is implemented")
        for k in ["acquisition_metadata", "spatial_reference", "temporal_reference"]:
            if value[k] is not None and not isinstance(value[k], dict):
                raise ProtocolError("Typed acquisition/reference metadata required")
        canonical(value)
        return cls(canonical(value))

    def document(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        Identity.from_dict(value)
        return dict(value)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._canonical).hexdigest()

    @property
    def participant(self) -> str:
        v = self.document()
        return str(v["dataset"] + ":" + v["subject"])


def validate_cohort(identities: list[Identity]) -> None:
    if not identities or len(identities) > 128:
        raise ProtocolError("Explicit bounded cohort required")
    seen = set()
    for identity in identities:
        v = identity.document()
        key = tuple(
            v[k]
            for k in [
                "dataset",
                "version",
                "subject",
                "session",
                "task",
                "run",
                "acquisition",
                "modality",
            ]
        )
        if key in seen:
            raise ProtocolError("Duplicate participant/session/task/acquisition record")
        seen.add(key)


def session_match(a: Identity, b: Identity, *, same_session: bool = True) -> dict[str, Any]:
    left, right = a.document(), b.document()
    fields = ["dataset", "version", "subject", "task", "modality", "run", "acquisition"]
    if same_session:
        fields.append("session")
    changed = [k for k in fields if left[k] != right[k]]
    return {
        "compatible": not changed,
        "mismatches": changed,
        "chronology_verified": False,
        "human_reliability_authorized": False,
    }


def now() -> str:
    return datetime.now(UTC).isoformat()


def chronology(left: Identity, right: Identity, sources: dict[str, bytes]) -> dict[str, Any]:
    a, b = left.document(), right.document()
    if any(a[k] != b[k] for k in ["dataset", "version", "subject", "task", "modality"]):
        raise ProtocolError("Chronology cannot link unrelated participant/task scopes")
    dates = []
    for item in [a, b]:
        claim = item["chronology"]
        if claim is None or claim["source_sha256"] not in sources:
            return {
                "verified": False,
                "order": None,
                "reason": "source acquisition timestamps unavailable",
            }
        raw = sources[claim["source_sha256"]]
        if len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != claim["source_sha256"]:
            raise ProtocolError("Acquisition timestamp source mismatch")
        source = json.loads(raw)
        if source.get("AcquisitionDateTime") != claim["acquired_at"]:
            raise ProtocolError("Source timestamp does not match chronology assertion")
        dates.append(timestamp(claim["acquired_at"]))
    return {
        "verified": True,
        "order": "left-before-right"
        if dates[0] < dates[1]
        else "right-before-left"
        if dates[1] < dates[0]
        else "same-time",
        "human_reliability_authorized": False,
    }
