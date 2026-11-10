"""Opt-in provider metadata verification; no registration creation or inference promotion."""

import hashlib
import json
import re
import urllib.error
import urllib.request
from typing import Any
from typing import Protocol as ProviderProtocol

from soma.human.model import checksum, now, timestamp
from soma.protocol.model import Protocol, ProtocolError


class RegistrationProvider(ProviderProtocol):
    def retrieve(self, identifier: str) -> dict[str, Any]: ...


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise ProtocolError("Registration metadata redirects are not authorized")


class OSF:
    """Public registration metadata only, fixed HTTPS origin, no auth headers or files."""

    def retrieve(self, identifier: str) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z0-9]{5}", identifier):
            raise ProtocolError("Invalid public OSF identifier")
        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(
            "https://api.osf.io/v2/registrations/" + identifier + "/",
            headers={"Accept": "application/vnd.api+json"},
        )
        with opener.open(request, timeout=20) as response:
            raw = response.read(1024**2 + 1)
        if len(raw) > 1024**2:
            raise ProtocolError("Registration metadata exceeds bound")
        return dict(json.loads(raw))


def inspect_registration(value: dict[str, Any], protocol: Protocol) -> dict[str, Any]:
    """Offline evidence is never elevated to a trusted source attestation."""
    checksum(protocol.fingerprint)
    return {
        "schema": "soma.registration.evidence/1.0.0",
        "provider": value.get("provider", "unknown"),
        "registration_id": value.get("registration_id"),
        "registered_protocol_id": protocol.document()["id"],
        "protocol_fingerprint": protocol.fingerprint,
        "status": "UNVERIFIED",
        "retrieval_status": "NOT_RETRIEVED_FROM_PROVIDER",
        "registration_timestamp": None,
        "verified_at": None,
        "unresolved": ["offline/local assertions do not attest provider evidence"],
        "independent_preregistration_established": False,
        "confirmatory_claim_allowed": False,
    }


def verify_registration(
    protocol: Protocol,
    identifier: str,
    *,
    opt_in: bool = False,
    provider: RegistrationProvider | None = None,
) -> dict[str, Any]:
    receipt = inspect_registration({"provider": "OSF", "registration_id": identifier}, protocol)
    if not opt_in:
        return receipt
    # Injected providers are useful for deterministic tests but cannot attest production evidence.
    trusted = provider is None
    source = provider or OSF()
    receipt["verified_at"] = now()
    try:
        value = source.retrieve(identifier)
        data = value["data"]
        attributes = data["attributes"]
        unresolved = []
        if data["id"] != identifier or data["type"] != "registrations":
            unresolved.append("provider identity/type mismatch")
        if attributes.get("public") is not True or attributes.get("withdrawn") is not False:
            unresolved.append("registration not public/active")
        date = attributes.get("date_registered")
        if not isinstance(date, str):
            unresolved.append("source registration timestamp unavailable")
        elif timestamp(date) > timestamp(receipt["verified_at"]):
            unresolved.append("invalid future source timestamp")
        description = attributes.get("description", "")
        fingerprints = re.findall(
            r"soma_protocol_fingerprint=([a-f0-9]{64})(?![a-f0-9])", description
        )
        identifiers = re.findall(r"soma_protocol_id=([A-Za-z0-9_-]+)", description)
        if fingerprints != [protocol.fingerprint] or identifiers != [protocol.document()["id"]]:
            unresolved.append("registered fingerprint/protocol correspondence missing or ambiguous")
        if not trusted:
            unresolved.append("injected provider is not independent production attestation")
        receipt.update(
            registration_url="https://osf.io/" + identifier + "/",
            registration_timestamp=date,
            retrieval_status="RETRIEVED_PUBLIC_METADATA",
            source_metadata_sha256=hashlib.sha256(
                json.dumps(value, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            status="PARTIAL_PUBLIC_METADATA_MATCH" if not unresolved else "UNVERIFIED",
            content_timestamp_attested=False,
            registered_content_immutability_verified=False,
            unresolved=unresolved,
            correspondence_scope="provider-held fingerprint claim, not attachment inspection",
        )
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        receipt.update(
            retrieval_status="UNAVAILABLE_OR_UNSUPPORTED",
            unresolved=["public provider retrieval failed; no authentication attempted"],
        )
    return receipt
