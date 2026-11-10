"""Versioned-artifact latency/memory observations; no machine-specific gates."""

import argparse
import hashlib
import json
import platform
import resource
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.sdk.results import (
    compare_results,
    create_result,
    inspect_result,
    load_result,
    migrate_legacy,
    save_result,
    validate_result,
    verify_provenance,
)


def measure(operation):
    times = []
    peak = 0
    for _ in range(5):
        tracemalloc.start()
        start = time.perf_counter()
        operation()
        times.append(time.perf_counter() - start)
        peak = max(peak, tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    return {
        "median_s": statistics.median(times),
        "python_tracemalloc_peak_bytes": peak,
        "repeats": len(times),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    observations = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for count in [128, 131072]:
            data = np.arange(count, dtype=np.float64)
            folder = root / str(count)
            folder.mkdir()
            (folder / "input.dat").write_bytes(data.tobytes())
            result = create_result(
                "experiment.manifest",
                {
                    "computation": "identity",
                    "inputs": {"input.dat": hashlib.sha256(data.tobytes()).hexdigest()},
                    "environment": {},
                    "assumptions": ["synthetic"],
                    "validation": {},
                    "limitations": ["format is not scientific validity"],
                },
                arrays={"values": data},
                provenance={"source": "arange"},
                method={"id": "identity", "version": "1"},
                parameters={},
                units={},
                dataset_identity="synthetic",
                subject_identity=None,
                spatial_reference=None,
                temporal_reference=None,
                statistical_estimand=None,
            )
            path = save_result(result, {"values": data}, folder / "artifact")
            legacy = folder / "legacy.json"
            legacy.write_text('{"schema_version":1,"parameters":{"value":1.25}}')
            counter = [0]

            def serialize(counter=counter, result=result, data=data, folder=folder):
                counter[0] += 1
                save_result(result, {"values": data}, folder / ("serialization-" + str(counter[0])))

            registry = Registry(
                Configuration(
                    roots={"fixture": str(folder)},
                    entries=[
                        Entry(
                            id="versioned",
                            kind="experiment",
                            label="synthetic",
                            root="fixture",
                            file="artifact/result.json",
                            synthetic=True,
                        )
                    ],
                )
            )
            with TestClient(create_app(registry), base_url="http://127.0.0.1") as client:

                def discover(client=client):
                    response = client.get("/api/experiments")
                    assert response.status_code == 200

                ops = {
                    "validation_metadata_only": lambda result=result: validate_result(result),
                    "inspection_metadata_only": lambda path=path: inspect_result(path),
                    "serialization": serialize,
                    "deserialization": lambda path=path: load_result(path),
                    "compatibility": lambda result=result: compare_results(result, result),
                    "migration": lambda legacy=legacy: migrate_legacy(
                        legacy, source_format="core-manifest-v1"
                    ),
                    "manifest_verification": lambda path=path, folder=folder: verify_provenance(
                        path, input_root=folder
                    ),
                    "Explorer_discovery_with_integrity": discover,
                }
                observations[str(data.nbytes)] = {name: measure(op) for name, op in ops.items()}
    result = {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "payload_bytes": [1024, 1048576],
        "observations": observations,
        "process_high_water_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        "memory_scope": (
            "tracemalloc observes Python-tracked allocations; "
            "RSS is whole-process high water including imports"
        ),
        "hashing": (
            "full byte snapshots and finite-value/content verification require reading "
            "complete linked arrays; inspect reads metadata only"
        ),
        "thresholds": "none; observations are platform-specific",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
