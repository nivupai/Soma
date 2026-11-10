"""Metadata-only graph projection for the Explorer; never opens a cache or arrays."""

import math
from collections import Counter
from dataclasses import asdict
from typing import Any, cast

from soma.workflow.model import Graph, WorkflowError
from soma.workflow.operations import builtins
from soma.workflow.privacy import redact_export


def graph_view(graph: Graph, record: dict[str, Any] | None = None) -> dict[str, Any]:
    order = builtins().validate(graph)
    if record is not None:
        rows = record.get("stages")
        if (
            record.get("schema") != "soma.workflow.run/1"
            or record.get("status") not in {"COMPLETE", "FAILED", "CANCELLED"}
            or not isinstance(rows, list)
            or len(rows) > len(graph.stages)
            or not isinstance(record.get("environment"), dict)
        ):
            raise WorkflowError("Invalid saved workflow status record")
        seen = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("stage") not in {s.id for s in graph.stages}
                or row["stage"] in seen
                or row.get("status") not in {"COMPLETE", "FAILED", "CANCELLED"}
                or type(row.get("cached")) is not bool
                or not isinstance(row.get("wall_s"), (int, float))
                or not math.isfinite(row["wall_s"])
                or row["wall_s"] < 0
            ):
                raise WorkflowError("Invalid stage observation in workflow record")
            seen.add(row["stage"])
        if record["status"] == "COMPLETE" and (
            len(rows) != len(graph.stages) or any(r["status"] != "COMPLETE" for r in rows)
        ):
            raise WorkflowError("Incomplete journal cannot claim complete workflow")
    statuses = {r["stage"]: r for r in (record or {}).get("stages", [])}
    levels = {a.id: 0 for a in graph.artifacts if a.producer is None}
    for s in order:
        levels[s.id] = max((levels[n] for n in s.inputs.values()), default=-1) + 1
        for output_id in s.outputs.values():
            levels[output_id] = levels[s.id] + 1
    layer_counts = Counter(levels.values())
    group_heights: dict[int, int] = {}
    for level, count in layer_counts.items():
        group_heights[level // 4] = max(group_heights.get(level // 4, 0), count)
    group_offsets: dict[int, int] = {}
    offset = 0
    for group in sorted(group_heights):
        group_offsets[group] = offset
        offset += group_heights[group] * 115 + 65
    counts: dict[int, int] = {}
    nodes = []
    for node in sorted(
        [
            *(asdict(a) | {"node_type": "artifact"} for a in graph.artifacts),
            *(asdict(s) | {"node_type": "stage"} for s in graph.stages),
        ],
        key=lambda n: (levels[n["id"]], n["id"]),
    ):
        identity = node["id"]
        level = levels[identity]
        row = counts.get(level, 0)
        counts[level] = row + 1
        observed = statuses.get(identity, {})
        status = observed.get("status", "NOT_RUN")
        nodes.append(
            {
                "id": identity,
                "node_type": node["node_type"],
                "position": {"x": (level % 4) * 245, "y": group_offsets[level // 4] + row * 115},
                "data": {
                    "label": identity,
                    "status": status,
                    "cache": "RECORDED_HIT"
                    if observed.get("cached")
                    else "RECORDED_MISS"
                    if observed
                    else "NOT_ASSESSED",
                    "validation": observed.get("validation", "DECLARATIONS_ONLY"),
                    "runtime_s": observed.get("wall_s"),
                    "reason": observed.get("reason"),
                    "metadata": node,
                },
            }
        )
    return cast(
        dict[str, Any],
        redact_export(
            {
                "schema": "soma.workflow.view/1",
                "id": graph.id,
                "nodes": nodes,
                "edges": [{"id": f"{a}--{b}", "source": a, "target": b} for a, b in graph.edges()],
                "environment": (record or {}).get("environment", {}),
                "status": (record or {}).get("status", "NOT_RUN"),
                "invalidation": (record or {}).get("invalidation"),
                "limitations": [
                    "read-only metadata view; no execution or array loading",
                    "recorded cache observations are not fresh verification",
                    "lineage does not establish anatomical/clinical validity",
                ],
            }
        ),
    )
