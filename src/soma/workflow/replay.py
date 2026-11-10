"""Four real workflow replays, selective reuse and existing Milestone 17 oracles."""

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np

from soma.pipeline.cache import decode
from soma.results.io import load_result
from soma.results.reproducibility import run_suite
from soma.workflow.examples import changed, example
from soma.workflow.model import invalidation
from soma.workflow.operations import builtins
from soma.workflow.runtime import Executor, identities


def replay(root: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"schema": "soma.workflow.replay/1", "workflows": {}}
    protocol = files("soma.resources").joinpath("workflow-tolerances-v1.json").read_bytes()
    report["tolerance_protocol_sha256"] = hashlib.sha256(protocol).hexdigest()
    bounds = json.loads(protocol)
    for family in ["eeg", "mri", "fmri", "source"]:
        graph = example(family)
        executor = Executor(builtins(), root / family)
        cold = executor.run(graph)
        warm = executor.resume(graph)
        altered = executor.run(changed(graph), previous=graph)
        if any(r["status"] != "COMPLETE" for r in [cold, warm, altered]):
            raise ValueError("Synthetic workflow failed: " + family)
        if not all(s["cached"] for s in warm["stages"]) or cold["outputs"] != warm["outputs"]:
            raise ValueError("Verified warm replay changed numerical content")
        keys = identities(graph, executor.registry, executor.environment)

        def value(stage: str, port: str, family: str = family, keys: dict[str, Any] = keys) -> Any:
            artifact, arrays = load_result(
                root / family / keys[stage]["cache_key"] / port / "result.json"
            )
            return decode(artifact["payload"]["values"], arrays, {})

        if family == "eeg":
            bands = value("bands", "bands")
            numerical = [*bands["mu"], *bands["beta"]]
        elif family == "mri":
            numerical = list(value("qc", "qc")["volumes_m3"].values())
        elif family == "fmri":
            roi = value("roi", "roi")
            numerical = [roi["mean_effect"], roi["mean_variance"]]
        else:
            source = value("reconstruct", "source")
            numerical = [*source["estimate"], *source["resolution_diagonal"]]
        byte_hashes = {}
        for stage in graph.stages:
            entry = root / family / keys[stage.id]["cache_key"]
            byte_hashes[stage.id] = {
                str(p.relative_to(entry)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(entry.rglob("*"))
                if p.is_file()
            }
        report["workflows"][family] = {
            "cold": cold["stages"],
            "warm": warm["stages"],
            "changed": altered["stages"],
            "invalidation": invalidation(graph, changed(graph)),
            "logical_keys": {n: k["logical_key"] for n, k in keys.items()},
            "cache_keys": {n: k["cache_key"] for n, k in keys.items()},
            "content_fingerprints": cold["outputs"],
            "file_fingerprints": byte_hashes,
            "numerical_summary": np.asarray(numerical, dtype=float).tolist(),
            "tolerance": bounds[family],
            "scientific_scope": "existing methods; synthetic numerical workflow only",
        }
        report["environment"] = executor.environment
    # Established analytical/reference cases are executed, not copied from old reports.
    report["milestone17_oracles"] = run_suite()
    report["all_passed"] = True
    report["cache_portability"] = (
        "exact environment only; numerical agreement cannot authorize reuse"
    )
    return report
