"""Thin resumable run artifacts reusing the established motor-imagery/cache backend."""

import json
import shutil
import warnings
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.datasets.eegbci import load_recording, recording_path
from soma.datasets.registry import REGISTRY
from soma.experiments.cache import canonical_id, publish_cache, staging_directory, validate_cache
from soma.experiments.cohort import _compute
from soma.experiments.config import CohortConfig
from soma.signal.cohort_synthetic import cohort_recording


def input_identity(root: Path, subject: int, run: int, cfg: CohortConfig) -> dict[str, Any]:
    if cfg.synthetic_seed is None:
        path = recording_path(root, subject, run)
        return {
            "dataset": cfg.dataset,
            "file_identifier": path.name,
            "subject": subject,
            "run": run,
            "sha256": sha256(path),
            "dataset_source": REGISTRY[cfg.dataset].source,
        }
    return {
        "dataset": "synthetic-cohort",
        "file_identifier": f"synthetic-S{subject:03d}R{run:02d}",
        "subject": subject,
        "run": run,
        "seed": cfg.synthetic_seed,
        "missing": cfg.synthetic_missing,
        "artifacts": cfg.synthetic_artifacts,
    }


def cached_record(
    root: Path,
    subject: int,
    run: int,
    cfg: CohortConfig,
    cache_root: Path,
    software: dict[str, Any],
) -> tuple[Path, dict[str, Any], bool]:
    source = input_identity(root, subject, run, cfg)
    fingerprint = source.get("sha256", canonical_id(source))
    parameters = {
        "source": json.loads(json.dumps(source)),
        "fingerprint": fingerprint,
        "motor": asdict(replace(cfg.motor, plots=False)),
        "bursts": asdict(cfg.bursts),
        "software": software,
    }
    key = canonical_id(parameters)
    cache = cache_root / key
    hit = validate_cache(cache, key)
    if not hit:
        raw = None
        staging = staging_directory(cache_root)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                if cfg.synthetic_seed is None:
                    raw, loaded = load_recording(root, subject, run)
                    source.update(loaded)
                else:
                    raw, truth = cohort_recording(
                        subject,
                        run,
                        cfg.synthetic_seed,
                        missing=cfg.synthetic_missing,
                        artifacts=cfg.synthetic_artifacts,
                    )
                    source["truth"] = truth
                _compute(raw, source, subject, run, cfg, staging)
            metadata = json.loads((staging / "metadata.json").read_text())
            metadata["ingest_processing_warnings"] = [str(item.message) for item in caught]
            (staging / "metadata.json").write_text(
                json.dumps(metadata, indent=2, allow_nan=False) + "\n"
            )
            publish_cache(staging, cache, key, parameters)
        except Exception as exc:
            if "caught" in locals():
                exc.record_warnings = [str(item.message) for item in caught]  # type: ignore[attr-defined]
            shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            if raw is not None:
                raw.close()
    metadata = json.loads((cache / "metadata.json").read_text())
    return cache, metadata, hit
