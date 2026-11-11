"""Explicit cached EEG inventory and M18 verified record cache; no dataset download."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.core.provenance import sha256
from soma.decoding.data import TrialDataset, _record
from soma.eeg_benchmark.protocol import validate_design
from soma.human.adapters import eeg
from soma.human.model import pseudonym
from soma.human.permissions import PermissionEvidence, check_permission
from soma.human.workflow import metadata
from soma.pipeline.cache import decode
from soma.results.io import load_result
from soma.workflow.model import Artifact, Graph, Stage, digest
from soma.workflow.runtime import Executor, Operation, Registry, content, identities


def inventory(root: Path, value: dict[str, Any], key: bytes) -> dict[str, Any]:
    validate_design(value)
    base = root / "MNE-eegbci-data/files/eegmmidb/1.0.0"
    subjects = sorted(int(p.name[1:]) for p in base.glob("S[0-9][0-9][0-9]") if p.is_dir())
    if len(subjects) != value["source_count"] + value["target_count"]:
        raise ValueError(
            "Cached cohort differs from the frozen size; do not silently substitute subjects"
        )
    rows = []
    for index, subject in enumerate(subjects):
        for run in value["runs"]:
            row = {
                "subject": subject,
                "run": run,
                "role": "source" if index < value["source_count"] else "target",
                "subject_key": pseudonym("eegmmidb", str(subject), key),
                "status": "MISSING",
                "sha256": None,
            }
            try:
                s = eeg(root, subject, run, key)
                s.verify_inputs()
                if s.identity.document()["task"] != "unilateral-imagery":
                    raise ValueError("Not unilateral imagery")
                row.update(
                    status="AVAILABLE",
                    sha256=dict(s.hashes)["image"],
                    identity_fingerprint=s.identity.fingerprint,
                )
            except (OSError, ValueError):
                row["reason"] = "missing or incompatible cached recording; retained"
            rows.append(row)
    return {
        "schema": "soma.eeg.benchmark-inventory/1.0.0",
        "records": rows,
        "fingerprint": digest(rows),
        "source_subjects": subjects[: value["source_count"]],
        "target_subjects": subjects[value["source_count"] :],
        "raw_data_downloaded": False,
        "history": "all65 cached subjects previously used; no untouched cohort",
    }


def record_operation(
    inputs: dict[str, Any], params: dict[str, Any], seed: int | None
) -> dict[str, Any]:
    c = inputs["record"]
    root = Path(c["root"])
    from soma.datasets.eegbci import recording_path

    path = recording_path(root, c["subject"], c["run"]).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or sha256(path) != c["sha256"]:
        raise ValueError("Changed or escaped source recording")
    permission = PermissionEvidence.from_dict(c["permission"])
    check = check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="analyze",
        source_content=Path(c["permission_source"]).read_bytes(),
    )
    if not check["allowed"]:
        raise ValueError("Use evidence does not support EEG analysis")
    p = params["configuration"]
    if c["run"] not in (4, 8, 12) or p["labels"] != {"T1": 0, "T2": 1}:
        raise ValueError("Incorrect imagery event mapping")
    arrays, frame, receipt = _record(root, c["subject"], c["run"], p)
    if sha256(path) != c["sha256"]:
        raise ValueError("Recording changed during preprocessing")
    decisions = [
        {"accepted": bool(r.get("accepted", False)), "reason": str(r.get("reason", ""))}
        for r in receipt["proposals"]
    ]
    return {
        "trials": {
            "X": arrays["X"],
            "context": arrays["context"],
            "rows": frame.to_dict("records"),
            "decisions": decisions,
            "n_proposed": len(receipt["proposals"]),
        }
    }


def record_graph(context: dict[str, Any], p: dict[str, Any]) -> tuple[Graph, Registry]:
    p = {
        k: p[k]
        for k in ["preprocessing", "channels", "quality", "epoch", "context", "fs_hz", "labels"]
    }
    meta = metadata("eegmmidb")
    meta.update(
        subject_identity=context["subject_key"],
        temporal_reference={"fs_hz": 160.0, "window_definition": {"epoch_s": p["epoch"]}},
        units={"voltage": "V"},
    )
    registry = Registry(
        [
            Operation(
                "benchmark.eeg.record",
                {"record": "benchmark.record"},
                {"trials": "benchmark.trials"},
                record_operation,
                algorithm_version="22.1",
            )
        ]
    )
    graph = Graph(
        "eeg-benchmark-record",
        (
            Artifact("record", "benchmark.record", meta, fingerprint=content(context)),
            Artifact("trials", "benchmark.trials", meta, producer="preprocess"),
        ),
        (
            Stage(
                "preprocess",
                "benchmark.eeg.record",
                {"record": "record"},
                {"trials": "trials"},
                {"configuration": p},
                algorithm_version="22.1",
            ),
        ),
    )
    return graph, registry


def load_dataset(
    root: Path,
    inv: dict[str, Any],
    p: dict[str, Any],
    permission: PermissionEvidence,
    source: Path,
    cache: Path,
    coverage_path: Path | None = None,
) -> tuple[TrialDataset, list[dict[str, Any]]]:
    if digest(inv["records"]) != inv["fingerprint"]:
        raise ValueError("Changed cohort inventory")
    decision = check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="analyze",
        source_content=source.read_bytes(),
    )
    if not decision["allowed"]:
        raise ValueError("Permission no longer supports cached analysis")
    arrays = []
    contexts = []
    frames = []
    coverage = []
    for item in inv["records"]:
        row = {**item, "status": "FAILED", "n_accepted": 0, "n_proposed": 0}
        try:
            if item["status"] != "AVAILABLE":
                raise ValueError("Scheduled input unavailable")
            c = {k: item[k] for k in ["subject", "run", "subject_key", "sha256"]}
            c.update(
                root=str(root.resolve()),
                permission=permission.document(),
                permission_source=str(source.resolve()),
            )
            from soma.datasets.eegbci import recording_path

            if sha256(recording_path(root, item["subject"], item["run"])) != item["sha256"]:
                raise ValueError("Source snapshot changed; cache reuse refused")
            graph, registry = record_graph(c, p)
            executor = Executor(registry, cache)
            run = executor.run(graph, inputs={"record": c}, input_root=root)
            if run["status"] != "COMPLETE":
                raise ValueError("Verified preprocessing stage failed")
            stage = identities(graph, registry, executor.environment)["preprocess"]
            envelope, numeric = load_result(cache / stage["cache_key"] / "trials/result.json")
            result = decode(envelope["payload"]["values"], numeric, {})
            frame = pd.DataFrame(result["rows"])
            counts = np.bincount(frame.label.to_numpy(int), minlength=2)
            row.update(
                n_accepted=len(frame),
                n_proposed=result["n_proposed"],
                class_counts=counts.tolist(),
                decisions=result["decisions"],
                workflow=run,
                graph=graph.to_dict(),
            )
            if int(np.min(counts)) < p["minimum_per_class_per_run"]:
                raise ValueError("Prespecified class count QC")
            arrays.append(result["X"])
            contexts.append(result["context"])
            frames.append(frame)
            row["status"] = "ELIGIBLE"
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            row["reason"] = type(exc).__name__ + ": " + str(exc)
        coverage.append(row)
    # All three runs are required; retain every recording and rejection.
    eligible = {
        s
        for s in [*inv["source_subjects"], *inv["target_subjects"]]
        if sum(r["status"] == "ELIGIBLE" and r["subject"] == s for r in coverage) == 3
    }
    if coverage_path is not None:
        from soma.simulations.calibration import atomic_json

        atomic_json(coverage_path, coverage)
    if not frames:
        raise ValueError("No eligible trials; coverage requires inspection")
    frame = pd.concat(frames, ignore_index=True)
    X = np.concatenate(arrays)
    context = np.concatenate(contexts)
    keep = np.flatnonzero(frame.subject.isin(eligible))
    if not len(keep):
        raise ValueError("No subjects satisfy the prespecified three-run QC")
    for row in coverage:
        if row["subject"] not in eligible:
            row["eligible_subject"] = False
        else:
            row["eligible_subject"] = True
    dataset = TrialDataset(
        np.asarray(X[keep], float),
        frame.label.to_numpy(dtype=np.int64)[keep],
        frame.iloc[keep].reset_index(drop=True),
        tuple(p["channels"]),
        p["fs_hz"],
        tuple(p["epoch"]),
        np.asarray(context[keep], float),
        tuple(p["context"]),
        {
            "inventory_fingerprint": inv["fingerprint"],
            "configuration_fingerprint": digest(p),
            "permission_fingerprint": permission.fingerprint,
        },
    )
    return dataset, coverage
