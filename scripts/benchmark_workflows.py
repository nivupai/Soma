"""Observed planning/lineage costs for branching DAGs; no timing acceptance gates."""

import argparse
import json
import platform
import resource
import statistics
import tempfile
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path
from typing import Any

from soma.workflow.examples import example
from soma.workflow.model import Artifact, Graph, Stage, invalidation
from soma.workflow.runtime import Executor, Operation, Registry, content, identities
from soma.workflow.view import graph_view


def identity(
    inputs: dict[str, Any], parameters: dict[str, Any], seed: int | None
) -> dict[str, Any]:
    return {"value": inputs["value"]}


def branching(count):
    meta = example("source").artifacts[0].metadata
    artifacts = [Artifact("input", "source.geometry", meta, fingerprint=content(1))]
    stages = []
    for i in range(count):
        parent = "input" if i == 0 else "a" + str((i - 1) // 2)
        name = "s" + str(i)
        node = "a" + str(i)
        stages.append(Stage(name, "benchmark.identity", {"value": parent}, {"value": node}))
        artifacts.append(Artifact(node, "source.geometry", meta, producer=name))
    return Graph("branching", tuple(artifacts), tuple(stages))


def measure(operation):
    times = []
    peak = 0
    for _ in range(3):
        tracemalloc.start()
        start = time.perf_counter()
        operation()
        times.append(time.perf_counter() - start)
        peak = max(peak, tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    return {"median_s": statistics.median(times), "python_peak_bytes": peak, "repeats": 3}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    registry = Registry(
        [
            Operation(
                "benchmark.identity",
                {"value": "source.geometry"},
                {"value": "source.geometry"},
                identity,
            )
        ]
    )
    observations = {}
    with tempfile.TemporaryDirectory() as d:
        for count in [10, 100, 1000]:
            graph = branching(count)
            executor = Executor(registry, Path(d) / str(count))
            changed = replace(
                graph,
                stages=(replace(graph.stages[0], parameters={"revision": 1}), *graph.stages[1:]),
            )
            observations[str(count)] = {
                "nodes": len(graph.artifacts) + len(graph.stages),
                "graph_validation": measure(graph.order),
                "cache_key_computation": measure(
                    lambda graph=graph, executor=executor: identities(
                        graph, registry, executor.environment
                    )
                ),
                "cache_lookup_resume_plan_miss": measure(
                    lambda graph=graph, executor=executor: executor.plan(graph)
                ),
                "invalidation": measure(
                    lambda graph=graph, changed=changed: invalidation(graph, changed)
                ),
                "lineage": measure(
                    lambda graph=graph, count=count: graph.lineage("a" + str(count - 1))
                ),
            }
        from soma.workflow.operations import builtins

        graph = example("source")
        executor = Executor(builtins(), Path(d) / "real-source")
        start = time.perf_counter()
        cold = executor.run(graph)
        cold_wall = time.perf_counter() - start
        assert cold["status"] == "COMPLETE", cold["stages"]
        small = {
            "cold_workflow_wall_s": cold_wall,
            "cache_verification_resume_plan": measure(
                lambda graph=graph, executor=executor: executor.plan(graph)
            ),
            "warm_workflow_execution": measure(lambda: executor.resume(graph)),
            "Explorer_metadata_projection": measure(lambda: graph_view(graph, cold)),
        }
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "graphs": observations,
        "small_real_source_workflow": small,
        "peak_process_RSS_MiB": rss / (1024**2 if platform.system() == "Darwin" else 1024),
        "scope": (
            "planning/metadata separated from four-operation science; "
            "Python allocations are not total native memory"
        ),
        "timing_thresholds": "none",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
