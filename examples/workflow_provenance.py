"""Public SDK: a small source DAG, verified warm replay and selective invalidation."""

import tempfile
from pathlib import Path

from soma.sdk.workflow import Executor, builtins, changed, example, invalidation


def run():
    graph = example("source")
    with tempfile.TemporaryDirectory() as root:
        executor = Executor(builtins(), Path(root) / "cache")
        cold = executor.run(graph)
        warm = executor.resume(graph)
        altered = executor.run(changed(graph))
        assert cold["status"] == warm["status"] == altered["status"] == "COMPLETE"
        assert cold["outputs"] == warm["outputs"] and all(s["cached"] for s in warm["stages"])
        return {
            "cold_stages": len(cold["stages"]),
            "verified_hits": sum(s["cached"] for s in warm["stages"]),
            "changed_cached_stages": [s["stage"] for s in altered["stages"] if s["cached"]],
            "invalidation": invalidation(graph, changed(graph)),
            "limitations": "toy numerical example, no anatomy or clinical readiness",
        }


if __name__ == "__main__":
    print(run())
