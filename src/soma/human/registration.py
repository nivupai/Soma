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


class AttachmentProvider(ProviderProtocol):
    """Read-only provider record retrieval, scoped to exact registration/file/version."""

    def retrieve_attachment(self, registration: str, file: str, version: str) -> dict[str, Any]: ...


class OSFAttachments:
    """Fixed-origin OSF API v2 metadata; no arbitrary links, auth, redirects or downloads.

    Current registered-file SHA256 is supported only for that exact current version.
    Older revision hashes, add-on files and archival failures remain unsupported.
    """

    def retrieve_attachment(self, registration: str, file: str, version: str) -> dict[str, Any]:
        _attachment_selectors(registration, file, version)
        opener = urllib.request.build_opener(NoRedirect())
        records = {}
        for role, suffix in {
            "registration": f"registrations/{registration}/",
            "file": f"registrations/{registration}/files/osfstorage/{file}/",
            "version": f"files/{file}/versions/{version}/",
        }.items():
            req = urllib.request.Request(
                "https://api.osf.io/v2/" + suffix, headers={"Accept": "application/vnd.api+json"}
            )
            with opener.open(req, timeout=20) as response:
                raw = response.read(1024**2 + 1)
            if len(raw) > 1024**2:
                raise ProtocolError("Provider metadata exceeds bound")
            records[role] = json.loads(raw)
        return records


def _attachment_selectors(registration: str, file: str, version: str) -> None:
    if not (
        re.fullmatch(r"[a-z0-9]{5}", registration)
        and re.fullmatch(r"[a-f0-9]{24}", file)
        and re.fullmatch(r"[1-9][0-9]{0,5}", version)
    ):
        raise ProtocolError("Explicit OSF registration/file/numeric revision required")


def verify_attachment(
    protocol: Protocol,
    identifier: str,
    file: str,
    version: str,
    attachment: bytes | None,
    *,
    opt_in: bool = False,
    provider: AttachmentProvider | None = None,
) -> dict[str, Any]:
    """Bind actual local attachment bytes to provider-reported immutable version/hash.

    Mock/injected adapters never produce production attestation. The concrete OSF
    adapter is trusted only for fixed-origin public metadata under documented frozen
    registration semantics; this is not a cryptographic timestamp authority.
    """
    _attachment_selectors(identifier, file, version)
    receipt: dict[str, Any] = {
        "schema": "soma.registration.attachment/1.0.0",
        "provider": "OSF",
        "registration_id": identifier,
        "registration_url": "https://osf.io/" + identifier + "/",
        "resource_version": f"osf:{identifier}:osfstorage:{file}:revision:{version}",
        "attachment_id": file,
        "version": version,
        "status": "UNVERIFIED",
        "protocol_fingerprint": protocol.fingerprint,
        "registered_protocol_id": protocol.document()["id"],
        "registration_timestamp": None,
        "attachment_sha256": None,
        "retrieval_status": "NOT_RETRIEVED",
        "verified_at": None,
        "independent_content_timestamp_attestation": False,
        "confirmatory_claim_allowed": False,
        "checks": {},
        "limitations": [
            "provider-reported version/timestamp, not cryptographic TSA or legal consent",
            "only current native OSF Storage registered-file revision supported",
        ],
    }
    if attachment is None:
        receipt.update(status="NOT_AVAILABLE", reasons=["local protocol attachment unavailable"])
        return receipt
    if len(attachment) > 1024**2:
        raise ProtocolError("Protocol attachment exceeds1MiB bound")
    digest = hashlib.sha256(attachment).hexdigest()
    receipt["attachment_sha256"] = digest
    try:
        from soma.protocol.model import SealedProtocol
        from soma.results.contracts import canonical

        attached = json.loads(attachment)
        if not isinstance(attached, dict):
            raise ProtocolError("Protocol attachment must be a JSON object")
        match = (
            SealedProtocol(canonical(attached)).protocol
            if attached.get("schema") == "soma.protocol.seal/1.0.0"
            else Protocol.from_dict(attached)
        )
        if match.fingerprint != protocol.fingerprint:
            raise ProtocolError("Attachment protocol mismatch")
    except (ValueError, KeyError, TypeError):
        receipt.update(
            status="MISMATCH", reasons=["attachment does not contain the exact Soma protocol"]
        )
        return receipt
    if not opt_in:
        receipt["reasons"] = ["provider access not opted in; local hash is not attestation"]
        return receipt
    receipt["verified_at"] = now()
    try:
        record = (provider or OSFAttachments()).retrieve_attachment(identifier, file, version)
        r, f, v = (record[k]["data"] for k in ["registration", "file", "version"])
        ra, fa, va = (x["attributes"] for x in [r, f, v])
        check = {
            "registration_identity": r["id"] == identifier and r["type"] == "registrations",
            "public_active_frozen": ra.get("public") is True
            and all(
                ra.get(k) is False
                for k in [
                    "withdrawn",
                    "archiving",
                    "pending_withdrawal",
                    "pending_registration_approval",
                ]
            ),
            "file_identity": f["id"] == file
            and f["type"] == "files"
            and fa.get("kind") == "file"
            and fa.get("provider") == "osfstorage",
            "file_registration_membership": f["relationships"]["node"]["links"]["related"]["href"]
            in {
                f"https://api.osf.io/v2/nodes/{identifier}/",
                f"https://api.osf.io/v2/registrations/{identifier}/",
            },
            "exact_version": v["id"] == version
            and v["type"] == "file_versions"
            and str(fa.get("current_version")) == version
            and v["links"]["self"] == f"https://api.osf.io/v2/files/{file}/versions/{version}/",
            "content_hash": fa.get("extra", {}).get("hashes", {}).get("sha256") == digest,
            "size": fa.get("size") == len(attachment) and va.get("size") == len(attachment),
            "protocol_correspondence": True,
        }
        registered, created = ra.get("date_registered"), va.get("date_created")
        check["source_timing"] = (
            isinstance(registered, str)
            and isinstance(created, str)
            and (timestamp(created) <= timestamp(registered) <= timestamp(receipt["verified_at"]))
        )
        receipt.update(
            checks=check,
            registration_timestamp=registered,
            attachment_created_at=created,
            source_metadata_sha256=hashlib.sha256(
                json.dumps(record, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            retrieval_status="RETRIEVED_PROVIDER_METADATA",
            verification_method="OSF frozen current revision, SHA256 and protocol inspection",
        )
        failed = [k for k, passed in check.items() if not passed]
        unknown = []
        if any(
            ra.get(k) is None
            for k in [
                "public",
                "withdrawn",
                "archiving",
                "pending_withdrawal",
                "pending_registration_approval",
            ]
        ):
            unknown.append("public_active_frozen")
        if fa.get("extra", {}).get("hashes", {}).get("sha256") is None:
            unknown.append("content_hash")
        if str(fa.get("current_version")) != version:
            unknown.append("exact_version")
        if registered is None or created is None:
            unknown.append("source_timing")
        contradiction = [k for k in failed if k not in unknown]
        receipt["provider_metadata"] = {
            "registration_type": r["type"],
            "public": ra.get("public"),
            "withdrawn": ra.get("withdrawn"),
            "archiving": ra.get("archiving"),
            "file_provider": fa.get("provider"),
            "current_version": fa.get("current_version"),
            "version_date_created": created,
        }
        receipt["retrieval_evidence"] = {
            "registration_endpoint": f"https://api.osf.io/v2/registrations/{identifier}/",
            "registered_file_endpoint": f"https://api.osf.io/v2/registrations/{identifier}/files/osfstorage/{file}/",
            "version_endpoint": f"https://api.osf.io/v2/files/{file}/versions/{version}/",
            "transport": "bounded HTTPS GET; fixed origin; redirects rejected",
        }
        trusted = provider is None
        receipt.update(
            status="MISMATCH"
            if contradiction
            else "PARTIALLY_VERIFIED"
            if failed
            else "VERIFIED_IMMUTABLE"
            if trusted
            else "PARTIALLY_VERIFIED",
            reasons=failed
            if failed
            else []
            if trusted
            else ["injected fixture provider; no independent production attestation"],
            independent_content_timestamp_attestation=not failed and trusted,
        )
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        receipt.update(
            status="UNVERIFIED",
            retrieval_status="UNAVAILABLE_OR_UNSUPPORTED",
            reasons=["provider evidence incomplete, unavailable or unsupported; no auth attempted"],
        )
    return receipt
