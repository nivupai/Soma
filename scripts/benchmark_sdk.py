"""Measured SDK/implementation calls on identical synthetic inputs; no CI thresholds."""

import argparse
import importlib.metadata
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

from examples.segmentation import inputs
from examples.surface_qc import mesh
from soma.benchmarks.segmentation import score as baseline_score
from soma.imaging.mesh_quality import mesh_quality as baseline_mesh
from soma.imaging.nifti import load_nifti as baseline_load
from soma.sdk.eeg import Signal, eeg_spectrum
from soma.sdk.fmri import Contrast, ModelConfig, contrast, fit
from soma.sdk.imaging import load_nifti, mesh_quality, save_nifti, score
from soma.sdk.provenance import read_manifest
from soma.sdk.synthetic import asymmetric, simulate_fmri
from soma.signal.spectral import welch as baseline_welch


def measure(operation):
    operation()
    values = []
    result = None
    for _ in range(5):
        start = time.perf_counter()
        result = operation()
        values.append(time.perf_counter() - start)
    size = len(json.dumps(result, default=lambda a: a.tolist(), allow_nan=False).encode())
    return {
        "median_wall_s": statistics.median(values),
        "min_wall_s": min(values),
        "repeats": len(values),
        "serialized_bytes": size,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--server-python", type=Path, default=Path(sys.executable))
    args = p.parse_args()
    prediction, reference = inputs()
    surface = mesh()
    signal = Signal(4e-6 * np.sin(2 * np.pi * 10 * np.arange(1600) / 160), 160)
    run, _ = simulate_fmri(seed=16042)
    config = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    with tempfile.TemporaryDirectory(prefix="soma-sdk-performance-") as directory:
        path = Path(directory) / "synthetic.nii.gz"
        save_nifti(asymmetric(), path)
        manifest = Path(directory) / "manifest.json"
        manifest.write_text('{"synthetic":true,"method":"identity-v1"}')
        volume = load_nifti(path)

        def spectrum(fn):
            s = fn(signal)
            return {"frequency": s.frequencies, "density": s.density}

        def glm():
            e = contrast(fit(run, config), Contrast("task", {"task": 1.0}))
            return {
                "effect": np.asarray(e.maps["effect_size"].dataobj),
                "confirmation": e.metadata["confirmatory_claim_allowed"],
            }

        operations = {
            "MRI_metadata": (
                lambda: load_nifti(path).geometry(),
                lambda: baseline_load(path).geometry(),
            ),
            "geometry_check": (
                lambda: {"same_grid": volume.same_grid(volume)},
                lambda: {"same_grid": volume.same_grid(volume)},
            ),
            "segmentation_metrics": (
                lambda: score(prediction, reference),
                lambda: baseline_score(prediction, reference),
            ),
            "EEG_PSD": (lambda: spectrum(eeg_spectrum), lambda: spectrum(baseline_welch)),
            "surface_QC": (lambda: mesh_quality(surface), lambda: baseline_mesh(surface)),
            "synthetic_GLM": (glm, glm),
            "provenance_read": (
                lambda: read_manifest(manifest),
                lambda: json.loads(manifest.read_text()),
            ),
        }
        measurements = {
            name: {"SDK": measure(pair[0]), "implementation": measure(pair[1])}
            for name, pair in operations.items()
        }
    cold = {}
    for module in ["soma.sdk", "soma.sdk.imaging", "soma.sdk.eeg", "soma.sdk.fmri"]:
        code = (
            "import time; t=time.perf_counter(); import importlib; importlib.import_module("
            + repr(module)
            + "); print(time.perf_counter()-t)"
        )
        cold[module] = float(
            subprocess.check_output([str(args.server_python), "-I", "-c", code], text=True)
        )
    clean_env = {
        k: v for k, v in os.environ.items() if k not in {"SOMA_EXPLORER_CONFIG", "PYTHONPATH"}
    }
    startup = None
    with tempfile.TemporaryDirectory(prefix="soma-sdk-server-") as directory:
        start = time.perf_counter()
        process = subprocess.Popen(
            [str(args.server_python.resolve()), "-I", "-m", "soma.sdk.explorer", "--port", "18316"],
            cwd=directory,
            env=clean_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError("Installed Explorer exited")
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:18316/api/catalog", timeout=0.3
                    ) as response:
                        assert response.status == 200
                        startup = time.perf_counter() - start
                        break
                except OSError:
                    time.sleep(0.1)
            if startup is None:
                raise TimeoutError("Explorer startup")
        finally:
            process.terminate()
            process.wait(timeout=10)
    result = {
        "platform": platform.system() + " " + platform.machine(),
        "python": platform.python_version(),
        "versions": {
            n: importlib.metadata.version(n)
            for n in ["soma-neuro", "numpy", "scipy", "mne", "nibabel", "nilearn", "SimpleITK"]
        },
        "measurements": measurements,
        "cold_import_s": cold,
        "installed_Explorer_startup_s": startup,
        "process_high_water_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        "RSS_scope": "whole process including imports, not attributable per call",
        "comparison_limits": (
            "same process sequential warm samples; shared algorithms; "
            "no speedup or clinical claim; no machine-specific threshold"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
