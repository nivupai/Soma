"""Read-only M25 aggregate receipts; never acquisition or inference over HTTP."""

from typing import Any

from fastapi import APIRouter

from soma.external_eeg.validation import M24_RELEASE, read_validation

from .registry import Registry, sanitize


def demo() -> dict[str, Any]:
    return {
        "schema": "soma.external-validation/1",
        "status": "BLOCKED",
        "dataset": "bnci2014-001",
        "release_id": M24_RELEASE,
        "synthetic_only": False,
        "mode": "HARMONIZED_FROZEN",
        "scientific_compatibility": "NOT_COMPARABLE",
        "acquisition_status": "BLOCKED",
        "human_external_subjects": 0,
        "human_external_sessions": 0,
        "human_external_trials": 0,
        "performance": [],
        "domain_shift": {
            "status": "METADATA_ONLY",
            "reason": "22-channel target reference differs from source64",
        },
        "blockers": [
            "No explicit acquisition authorization or reviewed complete manifest",
            "Current M20/M21 external use/export review unavailable",
            "Frozen reference/timing contract is not scientifically identical",
        ],
        "refitted_components": 0,
    }


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/external-validations")
    def listing() -> Any:
        return [{"id": "demo-external-validation", "label": "External validation readiness"}] + [
            {"id": e.id, "label": e.label}
            for e in registry.entries.values()
            if e.kind == "external-validation"
        ]

    @routes.get("/external-validations/{identity}")
    def report(identity: str) -> Any:
        if identity == "demo-external-validation":
            return demo()
        return sanitize(
            read_validation(registry.path(registry.get(identity, "external-validation")))
        )

    return routes
