"""Read-only external transfer readiness in the existing workbench."""

from typing import Any

from fastapi import APIRouter

from soma.external_eeg.contracts import candidate_audit
from soma.external_eeg.runtime import read_receipt

from .registry import Registry, sanitize


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/external-eeg")
    def listing() -> Any:
        return [
            {
                "id": "demo-external-eeg",
                "label": "External EEG permission and transfer audit",
                "synthetic": True,
            }
        ] + [
            {"id": e.id, "label": e.label, "synthetic": e.synthetic}
            for e in registry.entries.values()
            if e.kind == "external-eeg"
        ]

    @routes.get("/external-eeg/{identity}")
    def report(identity: str) -> Any:
        if identity == "demo-external-eeg":
            return candidate_audit()
        return sanitize(read_receipt(registry.path(registry.get(identity, "external-eeg"))))

    return routes
