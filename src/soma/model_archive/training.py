"""Source-only fitting with existing M22 preprocessing, M18 caches and M23 export."""

import os
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from threadpoolctl import threadpool_limits

from soma.core.provenance import sha256
from soma.datasets.human_mri import safe_local_output
from soma.decoding.data import TrialDataset
from soma.decoding.evaluation import FitAudit, fit_fold
from soma.decoding.metrics import classification_metrics
from soma.decoding.models import make_pipeline, require_unfitted
from soma.decoding.splits import inner_splits
from soma.eeg_benchmark.evaluation import bank, environment_snapshot
from soma.eeg_benchmark.protocol import MODELS
from soma.eeg_benchmark.statistics import bootstrap
from soma.external_eeg.models import freeze, predict
from soma.human.adapters import eeg
from soma.human.permissions import PermissionEvidence, check_permission
from soma.model_archive.archive import numerical_receipt, verify_release
from soma.model_archive.protocol import inspect_training
from soma.pipeline.cache import source_hash
from soma.protocol.model import SealedProtocol
from soma.workflow.model import digest


def source_inventory(root: Path, key: bytes) -> dict[str, Any]:
    rows = []
    for subject in range(1, 36):
        for run in (4, 8, 12):
            snapshot = eeg(root, subject, run, key)
            snapshot.verify_inputs()
            rows.append(
                {
                    "subject": subject,
                    "run": run,
                    "role": "source",
                    "subject_key": snapshot.identity.document()["subject"],
                    "status": "AVAILABLE",
                    "sha256": dict(snapshot.hashes)["image"],
                    "identity_fingerprint": snapshot.identity.fingerprint,
                }
            )
    return {
        "schema": "soma.model-source-inventory/1",
        "records": rows,
        "source_subjects": list(range(1, 36)),
        "target_subjects": [],
        "fingerprint": digest(rows),
        "raw_data_downloaded": False,
    }


def validate_source(data: TrialDataset, v: dict[str, Any]) -> None:
    frame = data.metadata
    if (
        data.provenance.get("dataset") != v["dataset"]
        or not set(frame.subject) <= set(v["subjects"])
        or not set(frame.run) <= set(v["runs"])
    ):
        raise ValueError("Target-data leakage or incorrect dataset label")
    if (
        list(data.channels) != v["contract"]["channels"]
        or data.fs != 160
        or data.interval != (1.0, 3.0)
        or data.X.dtype != np.dtype("float64")
        or set(data.y) != {0, 1}
    ):
        raise ValueError("Wrong source feature contract/precision")
    if frame.subject.nunique() < 3:
        raise ValueError("Three independent source units required")


def summarize_predictions(
    rows: list[dict[str, Any]], subjects: list[int], resamples: int
) -> dict[str, Any]:
    results = []
    for model in MODELS:
        units = []
        for subject in subjects:
            part = [r for r in rows if r["model"] == model and r["subject"] == subject]
            if not part:
                continue
            m = classification_metrics(
                np.array([r["label"] for r in part]), np.array([r["prediction"] for r in part])
            )
            units.append(
                {
                    "subject": subject,
                    "balanced_accuracy": m["balanced_accuracy"],
                    "left_recall": m["specificity"],
                    "right_recall": m["sensitivity"],
                    "n_trials": len(part),
                }
            )
        scores = [u["balanced_accuracy"] for u in units]
        results.append(
            {
                "model": model,
                "subjects": len(units),
                "planned_subjects": len(subjects),
                "missing_subjects": len(subjects) - len(units),
                "balanced_accuracy": bootstrap(scores, seed=24042, resamples=resamples)
                if len(scores) >= 2
                else None,
                "left_recall": float(np.mean([u["left_recall"] for u in units])),
                "right_recall": float(np.mean([u["right_recall"] for u in units])),
                "units": units,
            }
        )
    return {
        "methods": results,
        "sampling_unit": "subject",
        "interpretation": "reused source cohort; conditional fold evaluation, no untouched cohort",
        "external_replication": False,
    }


def archive_models(
    data: TrialDataset,
    sealed: SealedProtocol,
    output: Path,
    *,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
) -> dict[str, Any]:
    v = inspect_training(sealed)
    validate_source(data, v)
    if v["dataset"] == "eegmmidb":
        if (
            permission is None
            or notice is None
            or not check_permission(
                permission,
                dataset="eegmmidb",
                version="1.0.0",
                purpose="methods_research",
                action="analyze",
                source_content=notice,
            )["allowed"]
        ):
            raise ValueError(
                "Human model archiving requires current source-analysis permission evidence"
            )
    safe_local_output(output)
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    tick = time.perf_counter()
    code = source_hash()
    f = bank(data, v["configuration"])
    protocol_id = sealed.protocol.fingerprint
    source_id = data.fingerprint
    models = {}
    probe: dict[str, Any] = {"X": data.X, "powers": f.logpowers, "covariances": f.covariances}
    parity = {}
    with threadpool_limits(limits=1):
        for model in MODELS:
            pipeline = None
            prior = float(data.y.mean())
            if model != "dummy":
                pipeline = make_pipeline(
                    model, v["configuration"], v["parameters"][model], precomputed_covariance=True
                )
                require_unfitted(pipeline)
                pipeline.fit(f.input(model), data.y)
                original = (
                    pipeline.predict(f.input(model)),
                    pipeline.decision_function(f.input(model)),
                    pipeline.predict_proba(f.input(model))[:, 1]
                    if hasattr(pipeline, "predict_proba")
                    else None,
                )
            else:
                original = (
                    np.full(len(data.y), int(prior > 0.5)),
                    np.full(len(data.y), prior),
                    np.full(len(data.y), prior),
                )
            model_id = freeze(
                pipeline,
                model,
                v["contract"],
                {
                    "origin": "SYNTHETIC_SOURCE_FIT"
                    if v["dataset"] == "synthetic-external-v1"
                    else "EEGBCI_PROSPECTIVE_SOURCE_FIT",
                    "source_dataset": v["dataset"],
                    "source_fingerprint": source_id,
                    "protocol_fingerprint": protocol_id,
                    "parameters": v["parameters"][model],
                },
                output / "models" / model,
                prior=prior,
            )
            capsule = output / "models" / model / "result.json"
            replay = predict(capsule, model_id, v["contract"], data.X, f.logpowers, f.covariances)
            np.testing.assert_array_equal(original[0], replay[0])
            np.testing.assert_allclose(original[1], replay[1], **v["score_tolerance"])
            if original[2] is not None:
                np.testing.assert_allclose(original[2], replay[2], **v["score_tolerance"])
                probe[model + "_probabilities"] = np.asarray(original[2])
            probe[model + "_labels"] = np.asarray(original[0])
            probe[model + "_scores"] = np.asarray(original[1])
            parity[model] = {
                "labels_exact": True,
                "scores_exact": bool(np.array_equal(original[1], replay[1])),
                "score_max_abs_error": float(np.max(np.abs(original[1] - replay[1]))),
            }
            models[model] = {
                "id": model_id,
                "file": f"models/{model}/result.json",
                "sha256": sha256(capsule),
            }
        numerical_receipt(
            {"protocol_fingerprint": protocol_id, "source_fingerprint": source_id},
            probe,
            output / "probe",
            "soma.model-probe",
        )
        rows = []
        audit = FitAudit()
        for fold in inner_splits(data, np.arange(len(data.y)), 3):
            for model in MODELS:
                if model == "dummy":
                    pred = np.full(len(fold.test), int(data.y[fold.train].mean() > 0.5))
                else:
                    _, pred, _, _ = fit_fold(
                        f,
                        model,
                        v["configuration"],
                        fold,
                        v["parameters"][model],
                        audit,
                        phase="inner",
                    )
                for i, index in enumerate(fold.test):
                    rows.append(
                        {
                            "model": model,
                            "fold": fold.name,
                            "subject": int(data.metadata.iloc[index].subject),
                            "trial_id": str(data.metadata.iloc[index].trial_id),
                            "label": int(data.y[index]),
                            "prediction": int(pred[i]),
                        }
                    )
        (output / "source-cv-audit").mkdir()
        audit.save(output / "source-cv-audit")
    validation = summarize_predictions(rows, v["subjects"], v["bootstrap"]["resamples"])
    numerical_receipt(
        {"rows": rows, "validation": validation},
        {},
        output / "source-validation",
        "soma.model-source-validation",
    )
    if source_hash() != code:
        raise ValueError("Training code changed after seal; release refused")
    d = {
        "schema": "soma.model-release/1",
        "software_version": version("soma-neuro"),
        "dependency_versions": {"pyriemann": version("pyriemann")},
        "dataset": v["dataset"],
        "protocol": sealed.record(),
        "protocol_fingerprint": protocol_id,
        "source_fingerprint": source_id,
        "inventory_fingerprint": sealed.protocol.document()["optional_metadata"][
            "inventory_fingerprint"
        ],
        "models": models,
        "contract": v["contract"],
        "classes": v["classes"],
        "environment": environment_snapshot(),
        "implementation": code,
        "tolerance": v["score_tolerance"],
        "probe_file": "probe/result.json",
        "probe_sha256": sha256(output / "probe/result.json"),
        "parity": parity,
        "cohort": {
            "planned_subjects": len(v["subjects"]),
            "eligible_subjects": data.metadata.subject.nunique(),
            "recordings": data.metadata.recording.nunique(),
            "trials": len(data.y),
        },
        "wall_seconds": time.perf_counter() - tick,
        "historical_m22": False,
        "external_replication": False,
        "weights_redistribution": "NOT_AUTHORIZED",
        "supported_prediction": "M23 numeric kernels; explicit precomputed trial-local features",
        "unsupported": [
            "changed environment/build/code without separate validation",
            "missing reference channels",
            "target-fitted transforms",
            "unreviewed external data",
        ],
    }
    d["id"] = digest(d)
    numerical_receipt(d, {}, output / "manifest", "soma.model-release")
    reload = verify_release(
        output / "manifest/result.json",
        d["id"],
        output / "probe/result.json",
        permission=permission,
        notice=notice,
    )
    numerical_receipt(reload, {}, output / "reload", "soma.model-reload")
    return d
