"""Serial typed pipeline executor, resumable journals and immutable derivative publication."""

import hashlib
import json
import resource
import sys
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

from soma.core.provenance import manifest, sha256
from soma.imaging.volumes import Volume
from soma.pipeline.backends import backend_identity
from soma.pipeline.cache import StageCache, artifact_hash, source_hash
from soma.pipeline.contracts import InputRecord, ordered_graph
from soma.pipeline.derivatives import export_subject, private_output
from soma.pipeline.ingestion import load_input
from soma.pipeline.stages import execute_stage, graph
from soma.simulations.calibration import atomic_json


def configuration(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict) or cfg.get("schema_version") != 1:
        raise ValueError("MRI pipeline config schema_version1 required")
    required = ["affine_policy", "n4", "mask", "resampling", "backend", "surfaces", "visualization"]
    if any(k not in cfg for k in required):
        raise ValueError("Incomplete MRI pipeline config")
    if cfg["affine_policy"] not in ("error", "qform", "sform"):
        raise ValueError("Invalid affine policy")
    for group in ["n4", "resampling"]:
        if not isinstance(cfg[group].get("enabled"), bool):
            raise ValueError("Enabled stage flags must be booleans")
    if not isinstance(cfg["visualization"], bool) or not isinstance(
        cfg["mask"].get("apply_to_segmentation"), bool
    ):
        raise ValueError("Visualization/masking flags must be boolean")
    return dict(cfg)


def _is_type(value: Any, name: str) -> bool:
    return (
        (name == "Volume" and isinstance(value, Volume))
        or (name == "dict" and isinstance(value, dict))
        or (name == "record" and isinstance(value, dict))
        or (name == "list" and isinstance(value, list))
        or (name == "optionalVolume" and (value is None or isinstance(value, Volume)))
    )


def run_pipeline(
    record: InputRecord,
    config: dict[str, Any],
    output: Path,
    *,
    report_root: Path,
    cache_root: Path = Path("data/derived/mri-pipeline"),
    resume: bool = False,
    repair_cache: bool = False,
    dry_run: bool = False,
    interrupt_after: str | None = None,
) -> dict[str, Any]:
    stages = ordered_graph(graph(config), {"record"})
    if dry_run:
        return {
            "status": "dry-run",
            "record": record.key,
            "stages": [asdict(s) for s in stages],
            "writes_performed": False,
        }
    for p in [output, report_root, cache_root]:
        private_output(p)
    for p in [output.resolve(), report_root.resolve(), cache_root.resolve()]:
        if p == record.image.resolve().parent:
            raise ValueError("Output cannot be the source image directory")
    source_root = (record.source_root or record.image.parent).resolve()
    for candidate in [output.resolve(), report_root.resolve(), cache_root.resolve()]:
        if candidate.is_relative_to(source_root):
            allowed = record.dataset_type == "bids" and candidate.is_relative_to(
                source_root / "derivatives"
            )
            if not allowed:
                raise ValueError("Pipeline cannot write into an original source dataset")
    start = time.perf_counter()
    cpu = time.process_time()
    source_record = record.receipt()
    # Bind imported auxiliary content, resampling grids and masks in run/cache identities.
    auxiliary = {}
    for group in ["mask", "backend", "resampling"]:
        for key in ["path", "reference"]:
            if key in config[group]:
                auxiliary[group + ":" + key] = sha256(Path(config[group][key]))
    params = {
        "record": source_record,
        "config": config,
        "backend_implementation": backend_identity(config["backend"]["name"]),
        "auxiliary": auxiliary,
        "implementation": source_hash(),
        "output": str(output.resolve()),
        "software": {
            n: version(n) for n in ["soma-neuro", "numpy", "nibabel", "SimpleITK", "pybids"]
        },
    }
    if record.legacy and config["backend"]["name"] == "import":
        if sha256(Path(config["backend"]["path"])) == sha256(Path(record.legacy["reference"])):
            raise ValueError(
                "Reference annotation cannot be imported as an independent segmentation"
            )
    identity = hashlib.sha256(
        json.dumps(params, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    run_dir = report_root / record.key
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    journal = run_dir / "run.json"
    if run_dir.exists():
        if not resume:
            raise FileExistsError("Existing run directory; use resume only for an identical run")
        old = json.loads(journal.read_text())
        if old["identity"] != identity:
            raise ValueError("Resume identity differs; choose new output/report run")
        if old["status"] == "complete":
            for relative, h in old["derivatives"]["files"].items():
                if sha256(output / relative) != h:
                    raise ValueError("Published derivative changed; resume refused")
            if (
                sha256(output / "dataset_description.json")
                != old["derivatives"]["dataset_description_sha256"]
            ):
                raise ValueError("Derivative description changed")
            return {
                **old,
                "resume_verified": True,
                "cache_hits": 0,
                "verified_output_reuse": True,
                "stage_cache_reads": 0,
                "resume_wall_s": time.perf_counter() - start,
            }
    else:
        run_dir.mkdir()
    state: dict[str, Any] = {
        "identity": identity,
        "status": "running",
        "source": source_record,
        "config": config,
        "stages": [],
        "implementation": params["implementation"],
        "baseline_reference": "no reference used for segmentation",
    }
    atomic_json(journal, state)
    artifacts: dict[str, Any] = {"record": source_record}
    cache = StageCache(cache_root, repair=repair_cache, recover=resume)
    try:
        for spec in stages:
            inputs = {k: artifacts[k] for k in spec.inputs}
            if any(not _is_type(inputs[k], kind) for k, kind in spec.inputs.items()):
                raise ValueError("Stage input artifact type mismatch")
            parameters = {
                **spec.parameters,
                "backend_implementation": backend_identity(config["backend"]["name"])
                if spec.name == "segmentation"
                else {},
                "auxiliary": auxiliary
                if spec.name in ("preprocessing", "mask", "segmentation")
                else {},
            }

            def build(
                spec_name: str = spec.name,
                stage_inputs: dict[str, Any] = inputs,
                stage_parameters: dict[str, Any] = parameters,
            ) -> dict[str, Any]:
                return execute_stage(
                    spec_name,
                    stage_inputs,
                    stage_parameters,
                    lambda: load_input(record, affine_policy=config["affine_policy"]),
                )

            values, receipt = cache.run(spec.name, inputs, parameters, build)
            if set(values) != set(spec.outputs) or any(
                not _is_type(values[k], kind) for k, kind in spec.outputs.items()
            ):
                raise ValueError("Stage output contract violated")
            artifacts.update(values)
            state["stages"].append(
                {
                    "name": spec.name,
                    "status": "complete",
                    "contract": asdict(spec),
                    "cache": receipt,
                    "output_fingerprints": {k: artifact_hash(v) for k, v in values.items()},
                }
            )
            atomic_json(journal, state)
            if interrupt_after == spec.name:
                raise InterruptedError("Requested interruption after committed stage " + spec.name)
        if config["visualization"]:
            from soma.pipeline.plots import pipeline_figures

            pipeline_figures(run_dir, artifacts, state["stages"])
        atomic_json(run_dir / "qc.json", artifacts["qc"])
        atomic_json(run_dir / "backend.json", artifacts["backend_qc"])
        atomic_json(
            run_dir / "transforms.json",
            {
                "transforms": artifacts["preprocess_qc"]["transforms"],
                "legacy_alignment": artifacts["native"].metadata.get("legacy_alignment"),
                "native_geometry_preserved": artifacts["native"].geometry(),
            },
        )
        state["derivatives"] = export_subject(output, record, artifacts, identity, resume=resume)
        state.update(
            {
                "status": "complete",
                "cache_hits": sum(s["cache"]["hit"] for s in state["stages"]),
                "cache_misses": sum(not s["cache"]["hit"] for s in state["stages"]),
                "wall_s": time.perf_counter() - start,
                "cpu_s": time.process_time() - cpu,
                "process_peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / (1024**2 if sys.platform == "darwin" else 1024),
                "geometry": artifacts["processed"].geometry(),
                "qc": artifacts["qc"],
            }
        )
        atomic_json(journal, state)
        metadata = manifest(
            source_record,
            config,
            {"output": str(output), "report": str(run_dir)},
            config.get("seed"),
        )
        metadata["source_tree_sha256"] = source_hash()
        atomic_json(run_dir / "manifest.json", metadata)
        return state
    except Exception as exc:
        state.update(
            {
                "status": "interrupted" if isinstance(exc, InterruptedError) else "failed",
                "failed_stage": spec.name,
                "error": str(exc),
            }
        )
        atomic_json(journal, state)
        raise
