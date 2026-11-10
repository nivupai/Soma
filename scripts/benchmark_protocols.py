"""Observed metadata overhead; moderate registered graphs, never timing acceptance gates."""

import argparse
import json
import platform
import statistics
import time
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.protocol.binding import (
    base_graph,
    conformance,
    example_protocol,
    example_snapshot,
    graph_for,
    projection,
)
from soma.protocol.model import Protocol, anatomy, compare_protocols, methods, seal
from soma.protocol.replay import compare, history, plan, read_execution
from soma.workflow.model import Graph


def measure(operation):
    samples = []
    for _ in range(3):
        start = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - start)
    return {"median_s": statistics.median(samples), "repeats": 3}


def enlarged(groups):
    base = base_graph("source")
    stages, artifacts = [], []
    for i in range(groups):

        def rename(name, branch=i):
            return name if branch == 0 else f"branch{branch}-" + name

        stages.extend(
            replace(
                s,
                id=rename(s.id),
                inputs={k: rename(v) for k, v in s.inputs.items()},
                outputs={k: rename(v) for k, v in s.outputs.items()},
            )
            for s in base.stages
        )
        artifacts.extend(
            replace(a, id=rename(a.id), producer=rename(a.producer) if a.producer else None)
            for a in base.artifacts
        )
    graph = Graph("moderate-source", tuple(artifacts), tuple(stages))
    d = example_protocol("source").document()
    d["requirements"] = projection(graph)
    d["scientific"]["analysis_methods"] = methods(d["requirements"])
    d["scientific"]["anatomical_conventions"] = anatomy(d["requirements"])
    d["scientific"]["qc"]["required_stages"] = list(d["requirements"]["stages"])
    return Protocol.from_dict(d)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--histories", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    paths = [args.histories / "source" / f"execution-{i}/result.json" for i in [1, 2]]
    a, b = [read_execution(p) for p in paths]
    rows = {}
    for groups in [1, 25]:
        protocol = enlarged(groups)
        snapshot = example_snapshot(protocol)
        frozen = seal(protocol)
        graph = graph_for(protocol, snapshot, snapshot.document()["members"][0])
        d = protocol.document()
        rows[str(len(graph.stages))] = {
            "validation": measure(lambda d=d: Protocol.from_dict(d)),
            "sealing": measure(lambda protocol=protocol: seal(protocol)),
            "protocol_comparison": measure(
                lambda protocol=protocol: compare_protocols(protocol, protocol)
            ),
            "conformance": measure(
                lambda protocol=protocol, graph=graph: conformance(protocol, graph)
            ),
            "replay_planning": measure(
                lambda frozen=frozen, snapshot=snapshot: plan(
                    frozen, snapshot, cache_root=args.histories / "plan-cache"
                )
            ),
        }
    entries = [
        Entry(id=n, kind="execution", label=n, root="r", file=str(p.relative_to(args.histories)))
        for n, p in zip(["left", "right"], paths, strict=True)
    ]
    with TestClient(
        create_app(
            Registry(Configuration(roots={"r": str(args.histories.resolve())}, entries=entries))
        ),
        base_url="http://127.0.0.1",
    ) as client:

        def request():
            response = client.get("/api/replay-comparison?left=left&right=right")
            assert response.status_code == 200, response.text

        api = measure(request)
    result = {
        "platform": platform.platform(),
        "graphs": rows,
        "execution_history_2": measure(lambda: history(paths)),
        "drift_classification": measure(lambda: compare(a, b)),
        "explorer_comparison": api,
        "scientific_computation_included": False,
        "timing_acceptance_threshold": None,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
