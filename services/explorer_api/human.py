"""Explicitly registered local audit metadata; no execution or registration retrieval on GET."""

from typing import Any

from fastapi import APIRouter

from soma.human.workflow import read_execution

from .registry import Registry, read_json, sanitize


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/human-audits")
    def audits() -> Any:
        return [
            {
                "id": "demo-human-audit",
                "label": "Synthetic identity/session fixture",
                "synthetic": True,
            }
        ] + [
            {"id": e.id, "label": e.label, "synthetic": e.synthetic}
            for e in registry.entries.values()
            if e.kind == "human-audit"
        ]

    @routes.get("/human-audits/{identity}")
    def audit(identity: str) -> Any:
        if identity == "demo-human-audit":
            return {
                "schema": "soma.human.audit-view/1.0.0",
                "dataset": "synthetic-fixture-only",
                "status": "NOT_RUN",
                "synthetic": True,
                "registration": {
                    "status": "NOT_PROVIDED",
                    "external_preregistration_verified": False,
                },
                "warnings": [
                    "Fictional declarations only; no human data or scientific execution",
                    "Session identity does not establish chronology or reliability",
                ],
                "units": [
                    {
                        "participant_key": "fixture-only:fictional-person",
                        "session": s,
                        "task": "fictional-task",
                        "modality": "fMRI",
                        "status": "NOT_RUN",
                        "permission": "NOT_EVALUATED",
                        "eligibility": "NOT_EVALUATED",
                        "missing_preprocessing": "no audited derivatives or transform evidence",
                        "deviations": [],
                    }
                    for s in ["session-a", "session-b"]
                ],
            }
        entry = registry.get(identity, "human-audit")
        record = read_execution(registry.path(entry))
        units = []
        for u in record["units"]:
            d = u["identity"]
            units.append(
                {
                    "participant_key": d["dataset"] + ":" + d["subject"],
                    "session": d["session"],
                    "task": d["task"],
                    "run": d["run"],
                    "modality": d["modality"],
                    "status": u["status"],
                    "permission": u["eligibility"]["permission"]["status"],
                    "eligibility": u["eligibility"]["status"],
                    "missing_preprocessing": u["facts"].get("preprocessing", "not provided"),
                    "deviations": u["eligibility"]["reasons"],
                    "identity_fingerprint": u["identity_fingerprint"],
                    "lineage": u.get("graph") or u.get("planned_graph"),
                    "input_content_fingerprints": u["input_hashes"],
                }
            )
        registration = {"status": "NOT_PROVIDED", "external_preregistration_verified": False}
        if entry.metadata_file:
            claim = read_json(registry.path(entry, "metadata_file"))
            registration.update(
                status="LOCAL_RECEIPT_NOT_REVALIDATED",
                claimed_status=claim.get("status"),
                fingerprint_matches=claim.get("protocol_fingerprint")
                == record["protocol"]["protocol_fingerprint"],
            )
        return sanitize(
            {
                "schema": "soma.human.audit-view/1.0.0",
                "dataset": record["units"][0]["identity"]["dataset"],
                "status": record["status"],
                "synthetic": entry.synthetic,
                "units": units,
                "protocol_fingerprint": record["protocol"]["protocol_fingerprint"],
                "registration": registration,
                "warnings": [
                    "Local configured access only; keyed pseudonyms are not anonymity",
                    "Permission software checks do not establish legal authorization or consent",
                    "No human confirmation, anatomical readiness or reliability is established",
                ],
            }
        )

    return routes
