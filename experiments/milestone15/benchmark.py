"""Read-only in-process API benchmark; records aggregates, never participant paths."""

import json
import platform
import resource
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Registry


def main() -> None:
    config = Path("configs/explorer.local.json")
    registry = (
        Registry(Configuration.model_validate_json(config.read_text()))
        if config.exists()
        else Registry()
    )
    cases = {
        "catalog": "/api/catalog",
        "EEG_window_demo": "/api/eeg/demo-eeg/window?channels=C3,Cz,C4&points=1200",
        "PSD_TFR_bursts_demo": "/api/eeg/demo-eeg/analysis",
        "MRI_slice_demo": "/api/volumes/demo-mri/slice?x=20&y=16&z=12",
        "mesh_demo": "/api/sources/demo-source/mesh",
        "source_series_demo": "/api/sources/demo-source/series?index=10",
        "experiment_discovery": "/api/experiments",
        "fmri_demo": "/api/fmri/demo-fmri",
    }
    if "local-eeg" in registry.entries:
        cases.update(
            {
                "EEG_window_local": "/api/eeg/local-eeg/window?channels=C3..&points=1200",
                "PSD_TFR_bursts_local": "/api/eeg/local-eeg/analysis?channel=C3..",
                "MRI_slice_local": "/api/volumes/local-mri/slice?x=100&y=100&z=100",
                "mesh_template_artifact": "/api/sources/local-source/mesh",
                "source_PSF_artifact": "/api/sources/local-source/series?index=10",
                "fmri_existing_artifact": "/api/fmri/local-fmri",
            }
        )
    results: dict[str, Any] = {}
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as client:
        for name, url in cases.items():
            samples, parse_times = [], []
            size = 0
            for _ in range(9):
                before = time.perf_counter()
                response = client.get(url)
                samples.append(1000 * (time.perf_counter() - before))
                if response.status_code != 200:
                    raise RuntimeError(f"{name} failed with HTTP{response.status_code}")
                size = len(response.content)
                before = time.perf_counter()
                response.json()
                parse_times.append(1000 * (time.perf_counter() - before))
            results[name] = {
                "first_ms": samples[0],
                "warm_median_ms": float(np.median(samples[1:])),
                "warm_p95_ms": float(np.quantile(samples[1:], 0.95)),
                "response_bytes": size,
                "JSON_parse_median_ms": float(np.median(parse_times)),
            }
    receipt = {
        "scope": "TestClient in-process, serialized responses; no network latency;9 calls/case",
        "libraries": {
            name: version(name)
            for name in ["soma-neuro", "fastapi", "pydantic", "uvicorn", "numpy", "nilearn", "mne"]
        },
        "platform": platform.system() + "/" + platform.machine(),
        "measurements": results,
        "process_peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if platform.system() == "Darwin" else 1024),
        "limits": "No timing SLA; RSS includes caches/libraries; local data stays private",
    }
    Path("experiments/milestone15/api-performance.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(json.dumps({name: round(row["warm_median_ms"], 2) for name, row in results.items()}))


if __name__ == "__main__":
    main()
