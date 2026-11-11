"""M25 sealed acquisition/harmonization and fixed-state external validation."""

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from soma.core.provenance import sha256
from soma.datasets.human_mri import safe_local_output
from soma.decoding.data import TrialDataset
from soma.decoding.metrics import classification_metrics
from soma.eeg_benchmark.evaluation import bank
from soma.eeg_benchmark.protocol import MODELS
from soma.eeg_benchmark.statistics import bootstrap
from soma.external_eeg.acquisition import DATASETS, gate, snapshot, validate_manifest
from soma.external_eeg.contracts import feature_contract, parameters, plan, seal_plan
from soma.external_eeg.data import bnci_record, combine
from soma.human.evidence import EvidenceBundle, write_bundle
from soma.human.permissions import PermissionEvidence
from soma.model_archive.archive import inspect_archive, numerical_receipt
from soma.pipeline.cache import source_hash
from soma.protocol.model import Protocol, SealedProtocol, anatomy, methods, seal
from soma.results.io import inspect_result, load_result
from soma.workflow.model import digest
from soma.workflow.privacy import redact_export

M24_RELEASE = "8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85"


def harmonization(dataset: str = "bnci2014-001", mode: str = "HARMONIZED_FROZEN") -> dict[str, Any]:
    if dataset not in {*DATASETS, "synthetic-target-v25"} or mode not in (
        "EXACT_FROZEN",
        "HARMONIZED_FROZEN",
    ):
        raise ValueError(
            "Unsupported dataset/mode; external refitting requires a separate protocol"
        )
    synthetic = dataset == "synthetic-target-v25"
    target = feature_contract("synthetic-nine" if synthetic else "bnci-average-22")
    reason = {
        "bnci2014-001": "22-channel average is not the EEGBCI64-channel reference operator",
        "cho2017": (
            "Exact distribution, reference pool, cue timing and units not independently validated"
        ),
        "bnci2014-004": "Only3 bipolar channels: six required ROI channels absent",
        "synthetic-target-v25": (
            "Fictional independent draws; no human scientific comparability claim"
        ),
    }[dataset]
    return {
        "schema": "soma.external-harmonization/1",
        "planning_revision": 2,
        "technical_harmonization_allowed": mode == "HARMONIZED_FROZEN",
        "dataset": dataset,
        "version": "fictional-v25" if synthetic else DATASETS[dataset][0],
        "mode": mode,
        "source_release": M24_RELEASE if not synthetic else "SYNTHETIC_RELEASE_BOUND_BY_SEAL",
        "source_dataset": "eegmmidb" if not synthetic else "synthetic-external-v1",
        "source_contract": feature_contract(
            "eegbci-average-all-eeg" if not synthetic else "synthetic-nine"
        ),
        "target_contract": target if dataset in {"bnci2014-001", "synthetic-target-v25"} else None,
        "target_observation": {
            "eeg_channels": 9
            if synthetic
            else {"bnci2014-001": 22, "cho2017": 64, "bnci2014-004": 3}[dataset],
            "native_fs_hz": 160 if synthetic else 512 if dataset == "cho2017" else 250,
            "reference": "synthetic-nine"
            if synthetic
            else "all22 average proposal"
            if dataset == "bnci2014-001"
            else "bipolar C3/Cz/C4"
            if dataset == "bnci2014-004"
            else "NOT_VERIFIED",
            "contract_status": "COMPLETE_SYNTHETIC"
            if synthetic
            else "INCOMPATIBLE_REFERENCE"
            if dataset == "bnci2014-001"
            else "NOT_EXECUTABLE",
        },
        "conversion": {
            "input_units": "V" if synthetic else None if dataset == "cho2017" else "uV",
            "output_units": "V",
            "resample_ratio": [1, 1]
            if synthetic
            else [16, 25]
            if dataset.startswith("bnci")
            else [5, 16],
            "cue_offset_s": 0 if synthetic else 2 if dataset == "bnci2014-001" else None,
            "epoch_cue_s": [1.0, 3.0],
            "epoch_trial_s": [1.0, 3.0]
            if synthetic
            else [3.0, 5.0]
            if dataset == "bnci2014-001"
            else None,
        },
        "class_mapping": {"imagery_left": 0, "imagery_right": 1}
        if dataset == "cho2017"
        else {"1": 0, "2": 1},
        "excluded_classes": [3, 4] if dataset == "bnci2014-001" else [],
        "filter": target["filter"],
        "quality": parameters()["quality"],
        "source_artifact_flags": "reject",
        "missing_channels": "BLOCK; no interpolation",
        "subjects": list(range(1, 53 if dataset == "cho2017" else 10)),
        "sessions": ["T", "E"]
        if dataset in {"bnci2014-001", "synthetic-target-v25"}
        else ["distribution-specific; requires review"],
        "runs": list(range(1, 7)),
        "min_trials_per_class_per_run": 2,
        "compatible": synthetic,
        "compatibility_reason": reason,
        "independence": "fictional independent seed"
        if synthetic
        else "NOT_ESTABLISHED_BY_FILENAMES",
        "exclusion": "fixed source/QC only; retain missing planned participants and model failures",
        "statistics": {
            "unit": "subject",
            "bootstrap_resamples": 1999,
            "seed": 25042,
            "confidence": 0.95,
            "p_values": "NOT_SUPPORTED",
        },
        "refitting": "FORBIDDEN",
    }


def seal_validation(
    manifest_fingerprint: str,
    release_id: str,
    dataset: str = "bnci2014-001",
    mode: str = "HARMONIZED_FROZEN",
) -> SealedProtocol:
    v = harmonization(dataset, mode)
    if dataset != "synthetic-target-v25" and release_id != M24_RELEASE:
        raise ValueError("Authentic immutable M24 release required")
    d = seal_plan(plan(), manifest_fingerprint, {}).protocol.document()
    stage = d["requirements"]["stages"]["evaluate"]
    stage.update(
        implementation="benchmark.external.frozen-v25",
        algorithm_version="25.1",
        parameters={"harmonization_fingerprint": digest(v), "release_id": release_id},
    )
    d.update(
        id="external-frozen-v25",
        name="Frozen external model validation and readiness",
        version="2.0.0",
    )
    sci = d["scientific"]
    sci.update(
        question="Can archived source models consume external imagery under a frozen contract?",
        objective="No target fit; permissions and complete scientific contract first",
        estimand="external-participant mean balanced accuracy over fixed sessions/runs",
        preprocessing={"evaluate": stage["parameters"]},
        analysis_methods=methods(d["requirements"]),
        anatomical_conventions=anatomy(d["requirements"]),
        sensitivity_analyses=[],
    )
    sci["population"].update(
        dataset_namespace=v["dataset"],
        scope=manifest_fingerprint,
        inclusion=["sealed target cohort; complete required sessions and run/class coverage"],
        exclusion=[v["exclusion"]],
    )
    d["optional_metadata"] = {
        "external_validation": v,
        "manifest_fingerprint": manifest_fingerprint,
        "release_id": release_id,
    }
    return seal(Protocol.from_dict(d))


def inspect_validation(sealed: SealedProtocol) -> dict[str, Any]:
    m = sealed.protocol.document()["optional_metadata"]
    v = m["external_validation"]
    expected = seal_validation(m["manifest_fingerprint"], m["release_id"], v["dataset"], v["mode"])
    if expected.protocol.fingerprint != sealed.protocol.fingerprint:
        raise ValueError("Unapproved harmonization, selection or protocol amendment")
    return dict(v)


def runtime_request(runtime: Path, request: dict[str, Any], output: Path) -> dict[str, Any]:
    safe_local_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    packet = output.parent / (output.name + "-request.local.json")
    with packet.open("x") as stream:
        os.chmod(packet, 0o600)
        json.dump(request, stream)
    worker = Path(__file__).with_name("frozen_worker.py")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "SOMA_EXPLORER_CONFIG", "VIRTUAL_ENV"}
    }
    env.update(MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise ValueError("Explicit executable Python runtime required")
    result = subprocess.run(
        [
            str(runtime.absolute()),
            "-I",
            str(worker),
            str(packet.resolve()),
            str(output.resolve()),
        ],
        cwd=output.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode:
        raise ValueError("Frozen runtime refused execution: " + result.stderr[-2000:])
    e, numeric = load_result(output / "result.json")
    if e["payload"]["values"]["release_id"] != request["release_id"]:
        raise ValueError("Runtime model identity mismatch")
    return {"envelope": e, "arrays": numeric, "worker_sha256": sha256(worker)}


def summarize(
    data: TrialDataset, prediction: dict[str, Any], p: dict[str, Any], output: Path
) -> list[dict[str, Any]]:
    rows = []
    methods_out = []
    for model in MODELS:
        if model + "_labels" not in prediction:
            methods_out.append(
                {
                    "model": model,
                    "planned_subjects": len(p["subjects"]),
                    "complete_subjects": 0,
                    "missing_subjects": len(p["subjects"]),
                    "balanced_accuracy": None,
                    "class_recall": None,
                    "pooled_confusion_descriptive": [[0, 0], [0, 0]],
                    "prediction_coverage": 0,
                    "failures": len(p["subjects"]),
                }
            )
            continue
        labels = prediction[model + "_labels"]
        if len(labels) != len(data.y):
            raise ValueError("Predictions are not aligned with target trials")
        scores = []
        recalls = []
        matrix = np.zeros((2, 2), dtype=int)
        for subject in p["subjects"]:
            units = []
            for session in p["sessions"]:
                for run in p["runs"]:
                    ix = np.flatnonzero(
                        (data.metadata.subject == subject)
                        & (data.metadata.session == session)
                        & (data.metadata.run == run)
                    )
                    if (
                        len(ix)
                        and min(np.bincount(data.y[ix], minlength=2))
                        >= p["min_trials_per_class_per_run"]
                    ):
                        m = classification_metrics(data.y[ix], labels[ix])
                        units.append(m)
                        matrix += [[m["tn"], m["fp"]], [m["fn"], m["tp"]]]
            complete = len(units) == len(p["sessions"]) * len(p["runs"])
            row = {
                "model": model,
                "subject": subject,
                "status": "COMPLETE" if complete else "MISSING",
                "balanced_accuracy": float(np.mean([v["balanced_accuracy"] for v in units]))
                if complete
                else None,
            }
            rows.append(row)
            if complete:
                scores.append(row["balanced_accuracy"])
                recalls.append(
                    [
                        np.mean([v["specificity"] for v in units]),
                        np.mean([v["sensitivity"] for v in units]),
                    ]
                )
        methods_out.append(
            {
                "model": model,
                "planned_subjects": len(p["subjects"]),
                "complete_subjects": len(scores),
                "missing_subjects": len(p["subjects"]) - len(scores),
                "balanced_accuracy": bootstrap(scores, seed=25042, resamples=1999)
                if len(scores) >= 2
                else None,
                "class_recall": np.mean(recalls, axis=0).tolist() if recalls else None,
                "pooled_confusion_descriptive": matrix.tolist(),
                "prediction_coverage": len(labels),
                "failures": len(p["subjects"]) - len(scores),
            }
        )
    numerical_receipt({"rows": rows}, {}, output, "soma.external-participant-results")
    return methods_out


def execute(
    sealed: SealedProtocol,
    manifest: dict[str, Any],
    root: Path,
    archive: Path,
    runtime: Path,
    output: Path,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
    bundle: EvidenceBundle | None = None,
    references: dict[str, tuple[Path, str]] | None = None,
    *,
    synthetic_data: TrialDataset | None = None,
) -> dict[str, Any]:
    p = inspect_validation(sealed)
    meta = sealed.protocol.document()["optional_metadata"]
    release = inspect_archive(archive, meta["release_id"])
    synthetic = p["dataset"] == "synthetic-target-v25"
    safe_local_output(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {
        "schema": "soma.external-validation/1",
        "status": "BLOCKED",
        "mode": p["mode"],
        "dataset": p["dataset"],
        "release_id": release["id"],
        "protocol_fingerprint": sealed.protocol.fingerprint,
        "manifest_fingerprint": meta["manifest_fingerprint"],
        "source_code_sha256": source_hash(),
        "synthetic_only": synthetic,
        "human_external_subjects": 0,
        "human_external_sessions": 0,
        "human_external_trials": 0,
        "refitted_components": 0,
        "model_readiness": {
            m: {"fitted_state": "VERIFIED_IMMUTABLE", "inference": "NOT_EXECUTED"} for m in MODELS
        },
        "scientific_compatibility": "COMPATIBLE_SYNTHETIC_ONLY"
        if p["compatible"]
        else "NOT_COMPARABLE",
        "acquisition_status": "SYNTHETIC_NO_DOWNLOAD" if synthetic else "BLOCKED",
        "blockers": [],
        "performance": [],
        "domain_shift": {"status": "METADATA_ONLY", "reason": p["compatibility_reason"]},
        "independent_replication": False,
        "confirmatory_claim_allowed": False,
    }
    data = synthetic_data
    if synthetic:
        if (
            release["dataset"] != "synthetic-external-v1"
            or data is None
            or data.provenance.get("dataset") != "synthetic-target-v25"
            or meta["manifest_fingerprint"] != data.fingerprint
        ):
            raise ValueError("Synthetic/human dataset or snapshot mismatch")
        if p["target_contract"] != release["contract"]:
            raise ValueError("Frozen model feature contract mismatch")
    else:
        if synthetic_data is not None:
            raise ValueError("No synthetic substitution for human target recordings")
        if permission is None or notice is None or bundle is None or references is None:
            report["blockers"].append(
                "No current reviewed M20/M21 acquisition/use evidence supplied"
            )
        try:
            fp = validate_manifest(manifest)
            if fp != meta["manifest_fingerprint"] or manifest["dataset"] != p["dataset"]:
                raise ValueError("Changed dataset manifest after protocol seal")
            approved = gate(
                manifest,
                sealed.protocol.fingerprint,
                permission,
                notice,
                bundle,
                references,
                acquisition=False,
            )
            report["acquisition_status"] = approved["status"]
            report["blockers"].extend(approved["reasons"])
            if approved["status"] == "READY":
                inv = snapshot(root, manifest)
                report["verified_files"] = inv["verified_files"]
                if not inv["complete"]:
                    report["blockers"].append("Required snapshot files missing or changed")
        except (OSError, ValueError) as error:
            report["blockers"].append(
                str(error)
                if redact_export(str(error)) == str(error)
                else "Unavailable local snapshot/evidence"
            )
        if not p["compatible"]:
            report["blockers"].append(p["compatibility_reason"])
        if report["blockers"]:
            numerical_receipt(report, {}, output / "summary", "soma.external-validation")
            return report
        if p["dataset"] != "bnci2014-001":
            raise ValueError("Dataset parser not empirically validated; execution blocked")
        assert permission is not None and notice is not None
        pieces = []
        coverage = []
        for row in manifest["files"]:
            item = {"file": row["file"], "status": "FAILED"}
            try:
                d, decisions = bnci_record(
                    root / row["file"],
                    int(row["file"][1:3]),
                    row["file"][3],
                    row["sha256"],
                    permission,
                    notice,
                    p["version"],
                )
                item.update(
                    status="PREPROCESSED",
                    decisions=decisions,
                    proposed=len(decisions),
                    retained=0 if d is None else len(d.y),
                )
                if d is not None:
                    pieces.append(d)
            except (ValueError, OSError) as error:
                item["reason"] = type(error).__name__
            coverage.append(item)
        numerical_receipt(
            {"records": coverage}, {}, output / "record-coverage", "soma.external-record-coverage"
        )
        if not pieces:
            report["blockers"].append("No eligible target trials; private coverage retained")
            numerical_receipt(report, {}, output / "summary", "soma.external-validation")
            return report
        data = combine(pieces)
        report.update(
            trials_proposed=sum(r.get("proposed", 0) for r in coverage), trials_retained=len(data.y)
        )
        report["trials_rejected_or_excluded"] = report["trials_proposed"] - len(data.y)
    assert data is not None
    for row in data.metadata.itertuples():
        prefix = f"{p['dataset']}/s{row.subject:02}/{row.session}/r{row.run}"
        if (
            row.recording != prefix
            or not str(row.trial_id).startswith(prefix + "/t")
            or row.subject not in p["subjects"]
            or row.session not in p["sessions"]
            or row.run not in p["runs"]
        ):
            raise ValueError("Dataset/subject/session leakage or unplanned exclusion")
    if (
        list(data.channels) != p["target_contract"]["channels"]
        or data.fs != 160
        or data.interval != (1.0, 3.0)
    ):
        raise ValueError("Wrong units, feature order or sampling conversion")
    if data.provenance.get("contract") != p["target_contract"]:
        raise ValueError("Reference, unit or preprocessing contract mismatch")
    start = time.perf_counter()
    f = bank(data, parameters())
    numerical_receipt(
        {
            "contract": p["target_contract"],
            "dataset": p["dataset"],
            "version": p["version"],
            "protocol_fingerprint": sealed.protocol.fingerprint,
        },
        {"X": data.X, "powers": f.logpowers, "covariances": f.covariances},
        output / "features",
        "soma.external-features",
    )
    packet = output / "features/result.json"
    q = {
        "operation": "predict-synthetic" if synthetic else "predict-external",
        "archive": str(archive.resolve()),
        "release_id": release["id"],
        "packet": str(packet.resolve()),
        "packet_sha256": sha256(packet),
    }
    if not synthetic:
        assert (
            permission is not None
            and notice is not None
            and bundle is not None
            and references is not None
        )
        access = output / "access"
        access.mkdir(mode=0o700)
        (access / "permission.local.json").write_text(json.dumps(permission.document()))
        (access / "notice.local.txt").write_bytes(notice)
        write_bundle(bundle, access / "bundle.local.json")
        (access / "references.local.json").write_text(
            json.dumps(
                {k: {"root": str(v[0].resolve()), "relative": v[1]} for k, v in references.items()}
            )
        )
        q.update(
            permission=str((access / "permission.local.json").resolve()),
            notice=str((access / "notice.local.txt").resolve()),
            bundle=str((access / "bundle.local.json").resolve()),
            references=str((access / "references.local.json").resolve()),
        )
    result = runtime_request(runtime, q, output / "prediction")
    report.update(
        status="SYNTHETIC_COMPLETE" if synthetic else "HUMAN_COMPLETE_DESCRIPTIVE",
        performance=summarize(data, result["arrays"], p, output / "participant-results"),
        runtime_seconds=time.perf_counter() - start,
        worker_sha256=result["worker_sha256"],
        observed_synthetic_subjects=int(data.metadata.subject.nunique()),
        observed_synthetic_trials=len(data.y),
    )
    report["model_readiness"] = {
        m: {
            "fitted_state": "VERIFIED_IMMUTABLE",
            "inference": "PREDICTED" if m + "_labels" in result["arrays"] else "FAILED",
        }
        for m in MODELS
    }
    report["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        2**20 if sys.platform == "darwin" else 1024
    )
    # Target-only descriptive signal summaries; never re-estimate source reference matrices.
    if not synthetic:
        if snapshot(root, manifest)["snapshot_fingerprint"] != inv["snapshot_fingerprint"]:
            raise ValueError("Raw snapshot changed during frozen evaluation")
        report.update(
            human_external_subjects=int(data.metadata.subject.nunique()),
            human_external_sessions=int(
                data.metadata[["subject", "session"]].drop_duplicates().shape[0]
            ),
            human_external_trials=len(data.y),
        )
    report["domain_shift"] = {
        "status": "SYNTHETIC_ONLY" if synthetic else "OBSERVED_DESCRIPTIVE",
        "rms_uV": float(np.sqrt(np.mean(data.X**2)) * 1e6),
        "mean_log_power": float(f.logpowers.mean()),
        "class_counts": np.bincount(data.y, minlength=2).tolist(),
        "interpretation": "fictional acquisition variation, no physiological attribution",
    }
    if any(row["failures"] for row in report["performance"]):
        report["status"] = "SYNTHETIC_PARTIAL" if synthetic else "HUMAN_PARTIAL_DESCRIPTIVE"
    numerical_receipt(report, {}, output / "summary", "soma.external-validation")
    return report


def read_validation(path: Path) -> dict[str, Any]:
    e = inspect_result(path)["envelope"]
    if e["method"] != {"id": "soma.external-validation", "version": "1"} or e["payload"]["arrays"]:
        raise ValueError("Only aggregate external validation receipts are supported")
    d = dict(e["payload"]["values"])
    if (
        redact_export(d) != d
        or d["refitted_components"] != 0
        or d["independent_replication"] is not False
        or d["confirmatory_claim_allowed"] is not False
    ):
        raise ValueError("Private export or unsupported scientific claim")
    if d["synthetic_only"] != (d["dataset"] == "synthetic-target-v25"):
        raise ValueError("Incorrect external human/synthetic dataset labeling")

    def private(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) & {
                "subject",
                "trial_id",
                "predictions",
                "X",
                "powers",
                "covariances",
                "path",
                "root",
                "coef",
                "filters",
                "reference",
            }:
                raise ValueError("Restricted participant/model data in aggregate report")
            for item in value.values():
                private(item)
        elif isinstance(value, list):
            for item in value:
                private(item)

    private(d)
    if d["status"] == "BLOCKED" and (
        d["performance"]
        or any(
            d[k] != 0
            for k in ["human_external_subjects", "human_external_sessions", "human_external_trials"]
        )
    ):
        raise ValueError("Blocked human execution cannot contain accuracy outcomes")
    if d["synthetic_only"] and d["status"] not in {
        "BLOCKED",
        "SYNTHETIC_COMPLETE",
        "SYNTHETIC_PARTIAL",
    }:
        raise ValueError("Synthetic outcomes cannot become human validation")
    for method in d["performance"]:
        ci = method["balanced_accuracy"]
        if ci is not None and (
            ci["unit"] != "subject"
            or ci["n_subjects"] != method["complete_subjects"]
            or not 0 <= ci["lower"] <= ci["upper"] <= 1
        ):
            raise ValueError("Invalid participant uncertainty")
    return d


def compare_validation(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = ["dataset", "protocol_fingerprint", "release_id", "manifest_fingerprint", "mode"]
    same = all(k in left and left[k] == right.get(k) for k in keys)
    return {
        "status": "SAME_DECLARED_ESTIMAND" if same else "NOT_COMPARABLE",
        "numeric_comparison_authorized": same
        and left["status"] in {"SYNTHETIC_COMPLETE", "HUMAN_COMPLETE_DESCRIPTIVE"}
        and right["status"] in {"SYNTHETIC_COMPLETE", "HUMAN_COMPLETE_DESCRIPTIVE"},
        "cache_interchangeability": False,
        "historical_source_60_50_is_external": False,
    }
