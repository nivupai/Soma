"""Read-only aggregate model-release evidence; private fitted arrays never served."""

from typing import Any

from fastapi import APIRouter

from soma.model_archive.acquisition import acquisition_plan
from soma.results.io import inspect_result
from soma.workflow.privacy import redact_export

from .registry import Registry, sanitize


def demo() -> dict[str, Any]:
    return {
        "schema": "soma.model-release-summary/1",
        "status": "SYNTHETIC_INTERFACE_PREVIEW",
        "release_id": None,
        "protocol_fingerprint": None,
        "training_cohort": "No human model release selected",
        "models": ["dummy", "multiband_lr", "csp_lda", "riemann_mdm", "tangent_lr"],
        "fitted_state": "Select an audited aggregate release receipt",
        "source_validation": None,
        "external_acquisition": acquisition_plan()["status"],
        "human_external_accuracy": None,
        "historical_m22": False,
        "warnings": [
            "Newly archived state is not original M22 weights",
            "Source training or cross-validation is not independent external replication",
            "Private weights and participant predictions are not exposed",
        ],
    }


def read_summary(path: Any) -> dict[str, Any]:
    e = inspect_result(path)["envelope"]
    if (
        e["method"] != {"id": "soma.model-release-summary", "version": "1"}
        or e["payload"]["arrays"]
    ):
        raise ValueError("Only aggregate model-release summaries are viewable")
    d = e["payload"]["values"]
    if (
        set(d) != set(demo())
        or d["historical_m22"] is not False
        or d["human_external_accuracy"] is not None
    ):
        raise ValueError("Unsupported model-release summary or external performance claim")

    def private(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) & {
                "subject",
                "trial_id",
                "predictions",
                "coef",
                "intercept",
                "filters",
                "means",
                "reference",
                "units",
                "path",
                "root",
            }:
                raise ValueError("Private model/participant content in aggregate summary")
            for item in value.values():
                private(item)
        elif isinstance(value, list):
            for item in value:
                private(item)

    private(d)
    if redact_export(d) != d:
        raise ValueError("Private location in model summary")
    return dict(sanitize(d))


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/model-archives")
    def listing() -> Any:
        return [{"id": "demo-model-archive", "label": "Model archive interface preview"}] + [
            {"id": e.id, "label": e.label}
            for e in registry.entries.values()
            if e.kind == "model-archive"
        ]

    @routes.get("/model-archives/{identity}")
    def report(identity: str) -> Any:
        if identity == "demo-model-archive":
            return demo()
        return read_summary(registry.path(registry.get(identity, "model-archive")))

    return routes
