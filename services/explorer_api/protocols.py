"""Read-only protocol/replay metadata routes over the explicit local allowlist."""

from typing import Any, Literal

from fastapi import APIRouter

from soma.protocol.binding import example_protocol
from soma.protocol.binding import registry as operations
from soma.protocol.model import compare_protocols, read_seal, seal
from soma.protocol.replay import compare, read_execution
from soma.workflow.model import Graph

from .registry import Registry, sanitize


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    def protocol(identity: str) -> Any:
        if identity in {"demo-protocol-" + f for f in ["eeg", "mri", "fmri", "source"]}:
            return seal(example_protocol(identity.removeprefix("demo-protocol-")))
        return read_seal(registry.path(registry.get(identity, "protocol")))

    def execution(identity: str) -> Any:
        return read_execution(registry.path(registry.get(identity, "execution")))

    @routes.get("/protocols")
    def protocols() -> Any:
        return [
            {
                "id": "demo-protocol-" + f,
                "label": "Synthetic " + f.upper(),
                "status": "LOCAL_SEAL_NOT_PREREGISTRATION",
                "execution_status": "NOT_RUN",
            }
            for f in ["eeg", "mri", "fmri", "source"]
        ] + [
            {"id": e.id, "label": e.label, "status": "REGISTERED_LOCAL_SEAL"}
            for e in registry.entries.values()
            if e.kind == "protocol"
        ]

    @routes.get("/protocol-comparison")
    def revisions(left: str, right: str) -> Any:
        return sanitize(compare_protocols(protocol(left).protocol, protocol(right).protocol))

    @routes.get("/protocols/{identity}")
    def detail(identity: str) -> Any:
        value = protocol(identity).record()
        return sanitize(value)

    @routes.get("/replays")
    def replays(protocol_id: str | None = None) -> Any:
        entries = [e for e in registry.entries.values() if e.kind == "execution"]
        if len(entries) > 128:
            raise ValueError("Select a bounded execution registry")
        rows = []
        for e in entries:
            record = execution(e.id).record()
            p = record["protocol"]["protocol"]
            if protocol_id is None or protocol_id == p["id"]:
                rows.append(
                    {
                        "id": e.id,
                        "label": e.label,
                        "sequence": record["sequence"],
                        "protocol_id": p["id"],
                        "version": p["version"],
                        "status": record["status"],
                        "mode": record["mode"],
                    }
                )
        return sorted(rows, key=lambda x: (x["protocol_id"], x["sequence"], x["id"]))

    @routes.get("/replay-comparison")
    def comparison(
        left: str, right: str, mode: Literal["EXACT", "CONTROLLED", "EXPLORATORY"] = "EXACT"
    ) -> Any:
        return sanitize(compare(execution(left), execution(right), mode=mode))

    @routes.get("/replays/{identity}")
    def replay_detail(identity: str) -> Any:
        return sanitize(execution(identity).record())

    @routes.get("/replays/{identity}/lineage/{unit}")
    def lineage(identity: str, unit: int) -> Any:
        record = execution(identity).record()
        if unit < 0 or unit >= len(record["members"]):
            raise ValueError("Unknown scheduled unit")
        member = record["members"][unit]
        if not member.get("graph"):
            raise ValueError("No graph evidence for incomplete unit")
        graph = Graph.from_dict(member["graph"])
        operations().validate(graph)
        nodes = []
        for i, stage in enumerate(graph.stages):
            nodes.append(
                {
                    "id": stage.id,
                    "node_type": "stage",
                    "position": {"x": (i % 4) * 245, "y": (i // 4) * 230},
                    "data": {
                        "label": stage.id,
                        "status": member["status"],
                        "cache": "NOT_ASSESSED",
                        "validation": "RECORDED_CONFORMANCE",
                        "runtime_s": None,
                        "reason": None,
                        "metadata": {
                            "requirement_id": "method-" + stage.id,
                            "implementation": stage.implementation,
                        },
                    },
                }
            )
        for i, artifact in enumerate(graph.artifacts):
            nodes.append(
                {
                    "id": artifact.id,
                    "node_type": "artifact",
                    "position": {"x": (i % 4) * 245, "y": 115 + (i // 4) * 230},
                    "data": {
                        "label": artifact.id,
                        "status": member["status"],
                        "cache": "NOT_ASSESSED",
                        "validation": "RECORDED_METADATA",
                        "runtime_s": None,
                        "reason": None,
                        "metadata": artifact.metadata,
                    },
                }
            )
        return sanitize(
            {
                "id": graph.id,
                "status": member["status"],
                "nodes": nodes,
                "edges": [{"id": a + "--" + b, "source": a, "target": b} for a, b in graph.edges()],
                "environment": record["environment"],
                "limitations": ["recorded lineage; no fresh execution or cache verification"],
            }
        )

    return routes
