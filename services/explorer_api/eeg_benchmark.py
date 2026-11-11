"""Configured aggregate-only scientific benchmark views; GET never runs a benchmark."""

from typing import Any

from fastapi import APIRouter

from soma.eeg_benchmark.protocol import MODELS
from soma.eeg_benchmark.report import read_aggregate

from .registry import Registry, sanitize


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/eeg-benchmarks")
    def listing() -> Any:
        return [
            {
                "id": "demo-eeg-benchmark",
                "label": "Fictional protocol preview; no human evaluation",
                "synthetic": True,
            }
        ] + [
            {"id": e.id, "label": e.label, "synthetic": e.synthetic}
            for e in registry.entries.values()
            if e.kind == "eeg-benchmark"
        ]

    @routes.get("/eeg-benchmarks/{identity}")
    def report(identity: str) -> Any:
        if identity == "demo-eeg-benchmark":
            return {
                "schema": "soma.eeg.benchmark-preview/1.0.0",
                "status": "NOT_RUN",
                "models": list(MODELS),
                "warnings": [
                    "No fictional performance values are presented as human results",
                    "Historical EEGBCI reuse: held-out fitting is not external replication",
                    "Only configured aggregate receipts are visible; no benchmark executes on GET",
                ],
                "variants": [],
                "confirmatory_claim_allowed": False,
            }
        entry = registry.get(identity, "eeg-benchmark")
        return sanitize(read_aggregate(registry.path(entry)))

    return routes
