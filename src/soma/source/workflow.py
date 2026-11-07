"""Explicit source workflows, sealed configuration and portable result manifests."""

import hashlib
import json
import resource
import time
from pathlib import Path
from typing import Any

import mne
import numpy as np
import yaml

from soma.core.provenance import manifest, output_directory, sha256, write_json
from soma.datasets.eegbci import load_recording
from soma.source.forward import ForwardModel, build_forward
from soma.source.template import Template


def sealed_config(path: Path) -> dict[str, Any]:
    config: dict[str, Any] = yaml.safe_load(path.read_text())
    digest = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if path.with_suffix(".sha256").read_text().strip() != digest:
        raise ValueError("Source configuration differs from its sealed checksum")
    if "protocol" in config:
        sealed_config(Path(config["protocol"]))
    else:
        receipt = json.loads(path.with_name("source-modeling-freeze.json").read_text())
        if (
            sha256(path) != receipt["configuration_file_sha256"]
            or sha256(Path("docs/SOURCE_MODELING_PROTOCOL.md")) != receipt["document_sha256"]
        ):
            raise ValueError("Source protocol freeze receipt mismatch")
    return config


def study_forward(
    subject: int = 1,
    run: int = 4,
    data_dir: Path = Path("data/raw"),
    template_dir: Path = Path("data/anatomy"),
) -> ForwardModel:
    raw, _ = load_recording(data_dir, subject, run)
    try:
        return build_forward(
            Template(template_dir),
            list(raw.ch_names),
            cache=Path("data/derived/source/fsaverage-ico3-fwd.fif"),
        )
    finally:
        raw.close()


class RunReport:
    def __init__(
        self, output: Path, config: dict[str, Any], forward: ForwardModel, seed: int | None = None
    ) -> None:
        self.output = output_directory(output)
        self.started = time.perf_counter()
        self.cpu_started = time.process_time()
        self.config = config
        self.forward = forward
        self.seed = seed
        np.savez_compressed(
            output / "geometry.npz",
            source_head_m=forward.coordinates.points.xyz,
            lh_vertices=forward.vertices[0],
            rh_vertices=forward.vertices[1],
            source_basis_head=forward.native_free["source_nn"],
            sensor_head_m=np.array([c["loc"][:3] for c in forward.info["chs"]]),
            mri_to_head=np.asarray(forward.native_free["mri_head_t"]["trans"]),
            projector=forward.projector,
        )
        write_json(output / "forward.json", forward.diagnostics())

    def finish(self, result: dict[str, Any]) -> dict[str, Any]:
        result["runtime_s"] = time.perf_counter() - self.started
        result["cpu_time_s"] = time.process_time() - self.cpu_started
        result["runtime_scope"] = (
            "report/analysis stage, excluding forward preparation and EDF loading"
        )
        result["forward_preparation_runtime_s"] = self.forward.preparation_runtime_s
        # macOS ru_maxrss is bytes; Linux is KiB.
        import sys

        result["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1024**2 if sys.platform == "darwin" else 1024
        )
        result["memory_measurement"] = (
            "process high-water RSS, includes libraries and preceding stages"
        )
        write_json(self.output / "summary.json", result)
        metadata = manifest(
            self.forward.anatomy, self.config, {"output": str(self.output)}, self.seed
        )
        metadata["libraries"]["nibabel"] = __import__(
            "importlib.metadata", fromlist=["version"]
        ).version("nibabel")
        source_paths = sorted(Path("src/soma").rglob("*.py"))
        metadata["source_tree_sha256"] = hashlib.sha256(
            b"".join(str(p).encode() + p.read_bytes() for p in source_paths)
        ).hexdigest()
        metadata["result_files_sha256"] = {
            p.name: sha256(p) for p in self.output.iterdir() if p.is_file()
        }
        write_json(self.output / "manifest.json", metadata)
        return result


def synthetic_covariance(
    forward: ForwardModel,
    *,
    seed: int,
    samples: int = 16000,
    correlation: float = 0.35,
    std: float = 1e-6,
) -> tuple[Any, Any]:
    from soma.source.noise import NoiseModel

    n = len(forward.info["ch_names"])
    base = std**2 * correlation ** np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    rng = np.random.default_rng(seed)
    training = np.linalg.cholesky(base) @ rng.standard_normal((n, samples))
    noise = NoiseModel.estimate(training, tuple(forward.info["ch_names"]), forward.projector)
    covariance = mne.Covariance(
        noise.covariance.copy(), list(noise.channels), [], forward.info["projs"], samples - 1
    )
    return noise, covariance
