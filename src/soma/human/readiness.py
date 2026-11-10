"""Read-only evidence gates over M19 seals and M20 planning; never execution authorization."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from soma.human.adapters import Selection
from soma.human.evidence import EvidenceBundle, verify_bundle
from soma.human.model import Identity, chronology, validate_cohort
from soma.human.permissions import PermissionEvidence, permission_readiness
from soma.human.preprocessing import PreprocessingManifest, audit_manifest
from soma.human.registration import AttachmentProvider, verify_attachment
from soma.human.workflow import cohort_key, plan
from soma.protocol.model import ProtocolError, SealedProtocol, closed
from soma.workflow.model import digest

Status = Literal["READY", "BLOCKED", "INDETERMINATE", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class Gate:
    name: str
    status: Status
    reasons: tuple[str, ...]
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED", "INDETERMINATE", "NOT_APPLICABLE"}:
            raise ProtocolError("Unknown readiness gate")

    def document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }


def aggregate(gates: list[Gate]) -> Status:
    if not gates or any(g.status == "BLOCKED" for g in gates):
        return "BLOCKED"
    if any(g.status == "INDETERMINATE" for g in gates):
        return "INDETERMINATE"
    return "READY"


def session_audit(
    identities: list[Identity],
    *,
    chronology_required: bool = False,
    sources: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Identity alignment only; never manufactures visits, common spaces or QC."""
    validate_cohort(identities)
    values = [i.document() for i in identities]
    same_subject = len({(d["dataset"], d["version"], d["subject"]) for d in values}) == 1
    same_task = len({(d["task"], d["modality"]) for d in values}) == 1
    sessions = {d["session"] for d in values if d["session"] is not None}
    relationship = (
        "INDEPENDENT_DATASET_SCOPED_PARTICIPANTS"
        if not same_subject
        else (
            "REPEATED_SESSION"
            if len(sessions) >= 2
            else "REPEATED_RUN"
            if len({d["run"] for d in values}) >= 2
            else "REPEATED_ACQUISITION"
            if len({d["acquisition"] for d in values}) >= 2
            else "SINGLE_MEASUREMENT"
        )
    )
    gates = [
        Gate(
            "participant_scope",
            "READY" if same_subject else "BLOCKED",
            ("same dataset-scoped participant required; no cross-dataset joining",),
        ),
        Gate(
            "task_modality",
            "READY" if same_task else "BLOCKED",
            ("task label/modality agreement does not prove identical task implementation",),
        ),
        Gate(
            "explicit_sessions",
            "READY" if relationship == "REPEATED_SESSION" else "BLOCKED",
            ("two explicit sessions required for longitudinal readiness; runs are not visits",),
        ),
    ]
    for field in ["acquisition_metadata", "temporal_reference", "spatial_reference"]:
        encoded = [digest(d[field]) for d in values]
        complete = all(d[field] for d in values)
        gates.append(
            Gate(
                field,
                "READY" if complete and len(set(encoded)) == 1 else "INDETERMINATE",
                ("metadata agrees; shared scanner labels do not prove common space",),
            )
        )
    dates = []
    if chronology_required and same_subject and same_task:
        for first, second in zip(identities[:-1], identities[1:], strict=True):
            dates.append(chronology(first, second, sources or {}))
    established = bool(dates) and all(d["verified"] and d["order"] != "same-time" for d in dates)
    gates.append(
        Gate(
            "chronology",
            "READY"
            if chronology_required and established
            else "INDETERMINATE"
            if chronology_required
            else "NOT_APPLICABLE",
            ("source timestamps required; session labels do not establish intervals",),
        )
    )
    return {
        "schema": "soma.human.session-audit/1.0.0",
        "status": aggregate(gates),
        "relationship": relationship,
        "independent_participants": len({i.participant for i in identities}),
        "measurement_count": len(identities),
        "explicit_sessions": len(sessions),
        "gates": [g.document() for g in gates],
        "chronology_verified": established,
        "chronology": dates,
        "longitudinal_reliability_established": False,
        "common_anatomical_space_established": False,
    }


@dataclass(frozen=True)
class AttachmentRequest:
    registration: str
    file: str
    version: str
    content: bytes
    network: bool = False


def execution_readiness(
    protocol: SealedProtocol,
    selections: list[Selection],
    permission: PermissionEvidence,
    permission_source: Path,
    bundle: EvidenceBundle,
    references: dict[str, tuple[Path, str]],
    *,
    manifests: dict[str, PreprocessingManifest] | None = None,
    roots: dict[str, Path] | None = None,
    registration: AttachmentRequest | None = None,
    provider: AttachmentProvider | None = None,
    chronology_sources: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Recompute gates from live evidence. Historical receipts cannot upgrade readiness."""
    p = protocol.protocol
    identities = [s.identity for s in selections]
    validate_cohort(identities)
    d = p.document()
    policy = d.get("optional_metadata", {}).get(
        "research_readiness",
        {
            "schema": "soma.readiness.policy/1.0.0",
            "analysis": "existing-descriptive",
            "registration_required": False,
            "chronology_required": False,
        },
    )
    closed(policy, {"schema", "analysis", "registration_required", "chronology_required"})
    if (
        policy["schema"] != "soma.readiness.policy/1.0.0"
        or policy["analysis"]
        not in {"existing-descriptive", "longitudinal-descriptive", "confirmatory"}
        or any(
            type(policy[k]) is not bool for k in ["registration_required", "chronology_required"]
        )
    ):
        raise ProtocolError("Unsupported frozen readiness policy")
    b = bundle.document()
    scope_ok = all(
        (i.document()["dataset"], i.document()["version"]) == (b["dataset"], b["version"])
        for i in identities
    )
    protocol_ok = b["protocol_fingerprint"] == p.fingerprint and (
        "frozen-cohort:" + cohort_key(identities) in d["scientific"]["population"]["inclusion"]
    )
    integrity = verify_bundle(bundle, references)
    source_content = permission_source.read_bytes() if permission_source.is_file() else None
    use = permission_readiness(permission, source_content, bundle, references)
    base = (
        plan(protocol, selections, permission, permission_source)
        if protocol_ok
        else {
            "units": [
                {
                    "eligibility": {
                        "status": "BLOCKED",
                        "reasons": [
                            "frozen cohort/protocol scope mismatch; all selected records retained"
                        ],
                    }
                }
                for _ in selections
            ]
        }
    )

    gates = [
        Gate(
            "scope_protocol",
            "READY" if scope_ok and protocol_ok else "BLOCKED",
            ("dataset/version, frozen cohort and protocol seal must agree",),
            (p.fingerprint,),
        ),
        Gate(
            "evidence_bundle",
            "READY" if integrity["status"] == "READY" else "BLOCKED",
            ("content integrity and explicit review required; hashes do not prove authority",),
            (bundle.fingerprint,),
        ),
        Gate("permission", use["status"], tuple(use["reasons"]), (permission.fingerprint,)),
    ]
    units = []
    for selection, old in zip(selections, base["units"], strict=True):
        i = selection.identity
        ug = [
            Gate(
                "existing_protocol_conformance",
                "READY" if old["eligibility"]["status"] == "ELIGIBLE" else "BLOCKED",
                tuple(old["eligibility"]["reasons"]),
            )
        ]
        audit = None
        if i.document()["modality"] == "fMRI":
            manifest = (manifests or {}).get(i.fingerprint)
            if manifest is not None:
                if not any(
                    e["kind"] == "preprocessing" and e["sha256"] == manifest.fingerprint
                    for e in b["entries"]
                ):
                    raise ProtocolError("Preprocessing manifest not bound to evidence bundle")
                audit = audit_manifest(manifest, selection, roots or {})
            ug.extend(
                [
                    Gate(
                        "preprocessing",
                        audit["technical_status"] if audit else "BLOCKED",
                        ("audited derivatives and complete transforms required",),
                        (manifest.fingerprint,) if manifest else (),
                    ),
                    Gate(
                        "measured_QC",
                        audit["qc_status"] if audit else "INDETERMINATE",
                        ("measured motion/confounds/mask/QC evidence required",),
                    ),
                    Gate(
                        "scientific_preprocessing_adequacy",
                        "INDETERMINATE",
                        ("technical QC cannot establish anatomy/noise model suitability",),
                    ),
                ]
            )
        else:
            ug.append(Gate("fMRI_preprocessing", "NOT_APPLICABLE", ("not fMRI",)))
        gates.extend(
            Gate(i.fingerprint + ":" + g.name, g.status, g.reasons, g.evidence) for g in ug
        )
        units.append(
            {
                "identity_fingerprint": i.fingerprint,
                "participant_key": i.participant,
                "session": i.document()["session"],
                "run": i.document()["run"],
                "acquisition": i.document()["acquisition"],
                "task": i.document()["task"],
                "modality": i.document()["modality"],
                "status": aggregate(ug),
                "gates": [g.document() for g in ug],
                "preprocessing": audit,
            }
        )
    reg = (
        verify_attachment(
            p,
            registration.registration,
            registration.file,
            registration.version,
            registration.content,
            opt_in=registration.network,
            provider=provider,
        )
        if registration
        else {"status": "NOT_AVAILABLE", "independent_content_timestamp_attestation": False}
    )
    gates.append(
        Gate(
            "registration",
            "READY"
            if reg["status"] == "VERIFIED_IMMUTABLE"
            else "BLOCKED"
            if policy["registration_required"]
            else "NOT_APPLICABLE",
            ("immutable source/version required when frozen protocol requires registration",),
        )
    )
    session_reports = []
    if policy["analysis"] == "longitudinal-descriptive":
        for participant in sorted({i.participant for i in identities}):
            group = [i for i in identities if i.participant == participant]
            report = session_audit(
                group, chronology_required=policy["chronology_required"], sources=chronology_sources
            )
            session_reports.append(report)
            gates.append(
                Gate(
                    "sessions:" + participant,
                    report["status"],
                    ("longitudinal evidence required per participant; no trial pooling",),
                )
            )
        gates.append(
            Gate(
                "common_space_task_implementation",
                "INDETERMINATE",
                ("common anatomical frame and task implementation need reviewed correspondence",),
            )
        )
    gates.append(
        Gate(
            "human_confirmatory_inference",
            "BLOCKED" if policy["analysis"] == "confirmatory" else "NOT_APPLICABLE",
            ("human confirmation is never authorized by readiness",),
        )
    )
    return {
        "schema": "soma.research.readiness/1.0.0",
        "dataset": b["dataset"],
        "protocol_fingerprint": p.fingerprint,
        "bundle_fingerprint": bundle.fingerprint,
        "policy_fingerprint": digest(policy),
        "status": aggregate(gates),
        "gates": [g.document() for g in gates],
        "units": units,
        "sessions": session_reports,
        "registration": reg,
        "permission": use,
        "evidence_integrity": integrity,
        "confirmatory_claim_allowed": False,
        "legal_authorization_established": False,
        "consent_verified": False,
        "workflow_execution_authorized_by_report": False,
        "interpretation": "readiness evidence only; no analysis or reliability demonstrated",
    }


def validate_readiness(record: dict[str, Any]) -> None:
    """Native result seal handles content integrity; enforce non-promotion semantics too."""
    closed(
        record,
        {
            "schema",
            "dataset",
            "protocol_fingerprint",
            "bundle_fingerprint",
            "policy_fingerprint",
            "status",
            "gates",
            "units",
            "sessions",
            "registration",
            "permission",
            "evidence_integrity",
            "confirmatory_claim_allowed",
            "legal_authorization_established",
            "consent_verified",
            "workflow_execution_authorized_by_report",
            "interpretation",
        },
    )
    from soma.human.model import checksum

    for key in ["protocol_fingerprint", "bundle_fingerprint", "policy_fingerprint"]:
        checksum(record[key])
    if record.get("schema") != "soma.research.readiness/1.0.0":
        raise ProtocolError("Unsupported research readiness report")
    gates = [
        Gate(g["name"], g["status"], tuple(g["reasons"]), tuple(g["evidence"]))
        for g in record["gates"]
    ]
    required = {
        "scope_protocol",
        "evidence_bundle",
        "permission",
        "registration",
        "human_confirmatory_inference",
    }
    mapped = {g.name: g for g in gates}
    if len(mapped) != len(gates) or not required.issubset(mapped) or not record["units"]:
        raise ProtocolError("Readiness report has missing or duplicate requirements")
    for unit in record["units"]:
        local = [
            Gate(g["name"], g["status"], tuple(g["reasons"]), tuple(g["evidence"]))
            for g in unit["gates"]
        ]
        if unit["status"] != aggregate(local) or any(
            unit["identity_fingerprint"] + ":" + g.name not in mapped
            or mapped[unit["identity_fingerprint"] + ":" + g.name].status != g.status
            for g in local
        ):
            raise ProtocolError("Individual blocked requirements cannot be omitted")
    if record["status"] != aggregate(gates) or any(
        record[k] is not False
        for k in [
            "confirmatory_claim_allowed",
            "legal_authorization_established",
            "consent_verified",
            "workflow_execution_authorized_by_report",
        ]
    ):
        raise ProtocolError("Readiness cannot override blocked evidence or authorize inference")
    if record["registration"].get("status") == "VERIFIED_IMMUTABLE":
        if record["registration"].get("independent_content_timestamp_attestation") is not True:
            raise ProtocolError("Unsupported immutable registration claim")


def write_readiness(record: dict[str, Any], output: Path) -> None:
    """Existing M17 native result envelope, no additional provenance engine."""
    from soma.results.contracts import create_result
    from soma.results.io import save_result
    from soma.workflow.privacy import redact_export
    from soma.workflow.runtime import environment

    validate_readiness(record)
    if redact_export(record) != record:
        raise ProtocolError("Private locations/credentials forbidden in audit report")
    envelope = create_result(
        "experiment.manifest",
        {
            "computation": "research-readiness-audit",
            "inputs": {},
            "environment": environment(),
            "assumptions": ["read-only evidence validation"],
            "validation": {"scope": "evidence readiness, not legal or scientific certification"},
            "limitations": ["historical receipt must be recomputed before any new use"],
        },
        values=record,
        provenance={"protocol_fingerprint": record["protocol_fingerprint"]},
        interpretation_state="INDETERMINATE",
        method={"id": "soma.research.readiness", "version": "1"},
        parameters={},
        units={},
        dataset_identity=None,
        subject_identity=None,
        statistical_estimand="read-only readiness evidence; no inferred human effect",
    )
    save_result(envelope, {}, output)


def read_readiness(path: Path) -> dict[str, Any]:
    from soma.results.io import inspect_result

    e = inspect_result(path)["envelope"]
    if e["method"] != {"id": "soma.research.readiness", "version": "1"} or e["payload"]["arrays"]:
        raise ProtocolError("Metadata-only readiness result required")
    record = dict(e["payload"]["values"])
    validate_readiness(record)
    return record
