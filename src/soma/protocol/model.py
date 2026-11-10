"""Immutable local research declarations; seals are not independent preregistration."""

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soma import __version__
from soma.results.contracts import canonical
from soma.results.io import read_json
from soma.workflow.model import digest, identifier

SCHEMA = "soma.protocol/1.0.0"
SCIENTIFIC = {
    "question",
    "objective",
    "estimand",
    "population",
    "conditions",
    "preprocessing",
    "analysis_methods",
    "primary_outcomes",
    "inference",
    "sensitivity_analyses",
    "qc",
    "anatomical_conventions",
    "source_conductivity",
    "limitations",
}
ROOT = {
    "schema",
    "id",
    "name",
    "version",
    "scientific",
    "requirements",
    "replay_policy",
    "tolerances",
}
OPTIONAL = {"editorial", "optional_metadata", "registration", "amendment"}


class ProtocolError(ValueError):
    """Invalid, unverifiable or unauthorized research protocol operation."""


def closed(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    if (
        not isinstance(value, dict)
        or required - value.keys()
        or value.keys() - required - (optional or set())
    ):
        raise ProtocolError("Missing or unknown protocol fields")


def version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value
    ):
        raise ProtocolError("Explicit semantic protocol version required")
    parts = [int(x) for x in value.split(".")]
    return parts[0], parts[1], parts[2]


def methods(requirements: dict[str, Any]) -> dict[str, Any]:
    return {
        n: {k: s[k] for k in ["implementation", "algorithm_version", "parameters"]}
        for n, s in requirements["stages"].items()
    }


def anatomy(requirements: dict[str, Any]) -> dict[str, Any]:
    return {
        n: {
            k: a["metadata"][k]
            for k in ["units", "spatial_reference", "temporal_reference", "ontology"]
            if k in a["metadata"]
        }
        for n, a in requirements["artifacts"].items()
    }


def validate_document(document: dict[str, Any]) -> None:
    try:
        closed(document, ROOT, OPTIONAL)
        if document["schema"] != SCHEMA:
            raise ProtocolError("Unsupported protocol schema")
        identifier(document["id"])
        version(document["version"])
        if not isinstance(document["name"], str) or not document["name"]:
            raise ProtocolError("Protocol name required")
        if len(canonical(document)) > 1024**2:
            raise ProtocolError("Protocol exceeds 1 MiB bound")
        s = document["scientific"]
        closed(s, SCIENTIFIC)
        for key in ["question", "objective", "estimand"]:
            if not isinstance(s[key], str) or not s[key]:
                raise ProtocolError("Explicit scientific question/objective/estimand required")
        for key in ["conditions", "primary_outcomes", "limitations"]:
            if (
                not isinstance(s[key], list)
                or not s[key]
                or not all(isinstance(x, str) and x for x in s[key])
            ):
                raise ProtocolError("Explicit conditions/outcomes/limitations required")
        p = s["population"]
        closed(p, {"unit", "dataset_namespace", "scope", "inclusion", "exclusion"})
        if (
            p["unit"] not in {"subject", "synthetic-realization"}
            or not p["dataset_namespace"]
            or not isinstance(p["scope"], str)
            or not p["scope"]
        ):
            raise ProtocolError(
                "Independent subject/realization sampling unit required; never pooled trials"
            )
        if (
            not isinstance(p["inclusion"], list)
            or not p["inclusion"]
            or not isinstance(p["exclusion"], list)
            or not all(isinstance(x, str) and x for x in p["inclusion"] + p["exclusion"])
        ):
            raise ProtocolError("Prespecified inclusion and explicit exclusion rules required")
        inference = s["inference"]
        closed(inference, {"mode", "confirmatory_claim_allowed", "correction", "assumptions"})
        if (
            inference["mode"] not in {"descriptive", "exploratory"}
            or inference["confirmatory_claim_allowed"] is not False
        ):
            raise ProtocolError("Protocol replay does not authorize statistical confirmation")
        if (
            inference["correction"] not in {"none", "bh", "by", "bonferroni"}
            or not inference["assumptions"]
        ):
            raise ProtocolError("Explicit inference/multiple-comparison assumptions required")
        qc = s["qc"]
        closed(qc, {"required_stages", "missing_policy", "exclusion_policy"})
        if (
            qc["missing_policy"] != "retain_all_units_and_report"
            or qc["exclusion_policy"] != "prespecified_non_outcome_only"
        ):
            raise ProtocolError("Missing/excluded units cannot be selectively discarded")
        requirements = document["requirements"]
        closed(requirements, {"stages", "artifacts"})
        if not requirements["stages"] or len(requirements["stages"]) > 1000:
            raise ProtocolError("Bounded stage-to-requirement map required")
        if not isinstance(s["sensitivity_analyses"], list):
            raise ProtocolError("Sensitivity analyses must be explicitly declared")
        if s["analysis_methods"] != methods(requirements) or s["anatomical_conventions"] != anatomy(
            requirements
        ):
            raise ProtocolError(
                "Scientific method/anatomical declaration conflicts with stage requirements"
            )
        for n, params in s["preprocessing"].items():
            if requirements["stages"][n]["parameters"] != params:
                raise ProtocolError("Preprocessing and executable requirement disagree")
        if set(qc["required_stages"]) != set(requirements["stages"]):
            raise ProtocolError("Every executable stage requires QC/conformance evidence")
        for n, req in requirements["stages"].items():
            identifier(n)
            if (
                req["requirement_id"] != "method-" + n
                or not req["implementation"]
                or not req["algorithm_version"]
            ):
                raise ProtocolError("Applicable stage must bind its protocol requirement")
        policy = document["replay_policy"]
        closed(
            policy,
            {"controlled_axes", "platforms", "software_ranges", "seed_schedule", "synthetic_only"},
        )
        if set(policy["controlled_axes"]) - {
            "snapshot",
            "added_units",
            "session",
            "environment",
            "editorial_revision",
        }:
            raise ProtocolError("Unknown controlled replay authorization")
        if (
            policy["seed_schedule"]["algorithm"] != "sha256-unit-session-v1"
            or type(policy["seed_schedule"]["master_seed"]) is not int
        ):
            raise ProtocolError("Prespecified independent unit seed schedule required")
        for platform in policy["platforms"]:
            closed(platform, {"system", "machine", "python"})
            if platform["system"] not in {"Linux", "Darwin"} or platform["python"] not in {
                "3.11",
                "3.12",
            }:
                raise ProtocolError("Unsupported declared replay platform")
        bounds = document["tolerances"]
        closed(bounds, {"atol", "rtol", "axes", "units", "missing_policy", "scope"})
        if (
            bounds["missing_policy"] != "indeterminate"
            or bounds["scope"] != "selected_numerical_summaries"
        ):
            raise ProtocolError("Missingness and summary-level tolerance scope required")
        if any(type(bounds[k]) not in (int, float) or bounds[k] < 0 for k in ["atol", "rtol"]):
            raise ProtocolError("Finite nonnegative frozen tolerances required")
        if (
            not bounds["axes"]
            or len(bounds["axes"]) != len(bounds["units"])
            or len(set(bounds["axes"])) != len(bounds["axes"])
        ):
            raise ProtocolError("Explicit unique outcome axes and units required")
        if "amendment" in document:
            closed(
                document["amendment"],
                {
                    "parent_fingerprint",
                    "reason",
                    "authorization_reference",
                    "outcome_inspection",
                    "timing_evidence",
                },
            )
            a = document["amendment"]
            if (
                not re.fullmatch("[a-f0-9]{64}", a["parent_fingerprint"])
                or not a["reason"]
                or not a["authorization_reference"]
            ):
                raise ProtocolError("Explicit parent, reason and amendment reference required")
            if (
                a["outcome_inspection"] not in {"yes", "no", "unknown"}
                or a["timing_evidence"] != "LOCAL_UNVERIFIED"
            ):
                raise ProtocolError("Local amendments cannot certify prospective timing")
        digest(document)
    except ProtocolError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise ProtocolError("Invalid typed protocol declaration") from error


@dataclass(frozen=True)
class Protocol:
    _canonical: bytes

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Protocol":
        validate_document(value)
        return cls(canonical(value))

    def __post_init__(self) -> None:
        try:
            value = json.loads(self._canonical)
            validate_document(value)
            if canonical(value) != self._canonical:
                raise ProtocolError("Protocol must use canonical serialization")
        except (ValueError, TypeError, RecursionError) as error:
            raise ProtocolError("Invalid immutable protocol representation") from error

    def document(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        validate_document(value)
        return dict(value)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._canonical).hexdigest()

    @property
    def scientific_fingerprint(self) -> str:
        d = self.document()
        return digest(
            {k: d[k] for k in ["id", "scientific", "requirements", "replay_policy", "tolerances"]}
        )


@dataclass(frozen=True)
class SealedProtocol:
    _canonical: bytes

    def record(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        closed(
            value,
            {
                "schema",
                "protocol",
                "protocol_fingerprint",
                "scientific_fingerprint",
                "validation_receipt",
                "seal_sha256",
            },
        )
        p = Protocol.from_dict(value["protocol"])
        body = {k: v for k, v in value.items() if k != "seal_sha256"}
        if (
            value["schema"] != "soma.protocol.seal/1.0.0"
            or value["protocol_fingerprint"] != p.fingerprint
            or value["scientific_fingerprint"] != p.scientific_fingerprint
            or value["seal_sha256"] != hashlib.sha256(canonical(body)).hexdigest()
            or value["validation_receipt"].get("status") != "VALID_DECLARATIONS"
            or value["validation_receipt"].get("external_preregistration_verified") is not False
        ):
            raise ProtocolError("Protocol seal integrity/validation mismatch")
        return dict(value)

    @property
    def protocol(self) -> Protocol:
        return Protocol.from_dict(self.record()["protocol"])


def seal(protocol: Protocol) -> SealedProtocol:
    p = protocol.document()
    value = {
        "schema": "soma.protocol.seal/1.0.0",
        "protocol": p,
        "protocol_fingerprint": protocol.fingerprint,
        "scientific_fingerprint": protocol.scientific_fingerprint,
        "validation_receipt": {
            "validator": "soma.protocol/1",
            "producer_version": __version__,
            "status": "VALID_DECLARATIONS",
            "external_preregistration_verified": False,
            "registration_status": "UNVERIFIED_REFERENCE"
            if p.get("registration")
            else "NOT_DECLARED",
            "limitations": ["Local hash seal does not prove preregistration, authorship or timing"],
        },
    }
    value["seal_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return SealedProtocol(canonical(value))


def write_seal(value: SealedProtocol, path: Path) -> None:
    from soma.workflow.runtime import safe_root

    value.record()
    safe_root(path.parent, create=True)
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(value._canonical + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_seal(path: Path) -> SealedProtocol:
    result = SealedProtocol(canonical(read_json(path)))
    result.record()
    return result


def compare_protocols(left: Protocol, right: Protocol) -> dict[str, Any]:
    a, b = left.document(), right.document()
    changed = [k for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)]
    science = left.scientific_fingerprint != right.scientific_fingerprint
    status = (
        "IDENTICAL"
        if left.fingerprint == right.fingerprint
        else "SCIENTIFIC_AMENDMENT"
        if science
        else "EDITORIAL_OR_OPTIONAL"
    )
    relation = b.get("amendment", {}).get("parent_fingerprint") == left.fingerprint
    required = "new_exploratory_study" if science else "compatible_revision" if changed else "none"
    va, vb = version(a["version"]), version(b["version"])
    version_valid = not changed or (vb > va and (not science or vb[0] > va[0]))
    return {
        "status": status,
        "changed_fields": changed,
        "scientific_change": science,
        "required_revision": required,
        "major_revision_required": science,
        "version_declaration_valid": version_valid,
        "explicit_parent_amendment": relation,
        "compatible_scientific_methods": not science,
        "confirmatory_replication_authorized": False,
    }


def amend(
    protocol: Protocol,
    new_document: dict[str, Any],
    *,
    reason: str,
    authorization_reference: str,
    outcome_inspection: str = "unknown",
) -> Protocol:
    value = copy.deepcopy(new_document)
    value["amendment"] = {
        "parent_fingerprint": protocol.fingerprint,
        "reason": reason,
        "authorization_reference": authorization_reference,
        "outcome_inspection": outcome_inspection,
        "timing_evidence": "LOCAL_UNVERIFIED",
    }
    result = Protocol.from_dict(value)
    if not compare_protocols(protocol, result)["version_declaration_valid"]:
        raise ProtocolError("Structural amendment requires an increasing major scientific revision")
    return result
