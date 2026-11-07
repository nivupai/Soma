"""Development, explicit protocol freezing, and gated prospective evaluation."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from soma.core.provenance import manifest, sha256
from soma.datasets.eegbci import fetch
from soma.decoding.config import digest, identity, read_protocol
from soma.decoding.data import combine_trials, load_trials
from soma.decoding.evaluation import FitAudit, adaptation, choose_parameters, evaluate
from soma.decoding.features import FeatureBank, build_bank, covariance_parameters
from soma.decoding.synthetic import simulate_decoding
from soma.simulations.calibration import atomic_json


def run_development(
    root: Path,
    subjects: tuple[int, ...],
    config: Path,
    output: Path,
    mode: str,
    *,
    cache: Path = Path("data/derived/decoding-trials"),
    plots: bool = True,
) -> dict[str, Any]:
    protocol, _ = read_protocol(config)
    if "protocol" in protocol:
        raise ValueError("Development command expects the original development protocol")
    dataset, records = load_trials(root, subjects, protocol, cache)
    bank = build_bank(dataset, covariance_parameters(protocol))
    if mode == "adaptation":
        result = adaptation(bank, protocol, output, plots=plots)
    else:
        result = evaluate(bank, protocol, mode, output, plots=plots)
    atomic_json(output / "record_coverage.json", records)
    dataset.metadata.to_csv(output / "trials.csv", index=False)
    return result


def run_nulls(
    bank: FeatureBank, protocol: dict[str, Any], output: Path, repetitions: int | None = None
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    statuses = []
    n_repetitions = protocol["null_repetitions"] if repetitions is None else repetitions
    if not isinstance(n_repetitions, int) or n_repetitions < 1:
        raise ValueError("Null replications must be a positive integer")
    for repetition in range(n_repetitions):
        rng = np.random.default_rng(np.random.SeedSequence([protocol["seed"], 999, repetition]))
        labels = bank.dataset.y.copy()
        for indices in bank.dataset.metadata.groupby(["subject", "run"]).indices.values():
            labels[indices] = rng.permutation(labels[indices])
        child = output / f"permutation-{repetition:03d}"
        result = evaluate(
            bank,
            protocol,
            "cross-subject",
            child,
            models=tuple(protocol["null_models"]),
            labels=labels,
            plots=False,
        )
        statuses.append(result["status"])
        table = pd.read_csv(child / "metrics_subject.csv")
        for model, frame in table.groupby("model"):
            rows.append(
                {
                    "permutation": repetition,
                    "model": model,
                    "mean_subject_balanced_accuracy": float(frame.balanced_accuracy.mean()),
                    "n_subjects": len(frame),
                    "failed_folds": result["failures"],
                }
            )
        pd.DataFrame(rows).to_csv(output / "null_scores.csv", index=False)
    atomic_json(
        output / "manifest.json",
        manifest(
            {"dataset_fingerprint": bank.dataset.fingerprint},
            {
                "protocol_sha256": digest(protocol),
                "scheme": "independent within-subject/run label permutations; full nested refits",
                "software": identity(),
                "replications": n_repetitions,
                "assumption": "within-run exchangeability; temporal correlation caveat",
            },
            {"output": str(output.resolve())},
            protocol["seed"],
        ),
    )
    return {
        "status": "complete" if all(s == "complete" for s in statuses) else "partial",
        "output": str(output),
        "permutations": len(pd.DataFrame(rows).permutation.unique()),
    }


def synthetic_workflow(
    config: Path, output: Path, seed: int = 42, plots: bool = True
) -> dict[str, Any]:
    protocol, _ = read_protocol(config)
    output.mkdir(parents=True, exist_ok=False)
    dataset, truth = simulate_decoding(seed=seed)
    bank = build_bank(dataset, covariance_parameters(protocol))
    atomic_json(output / "truth.json", truth)
    result = evaluate(bank, protocol, "cross-subject", output / "cross-subject", plots=plots)
    evaluate(bank, protocol, "within-subject", output / "within-subject", plots=plots)
    null, _ = simulate_decoding(seed=seed + 1, null=True)
    evaluate(
        build_bank(null, covariance_parameters(protocol)),
        protocol,
        "cross-subject",
        output / "independent-label-null",
        models=("multiband_lr", "csp_lda", "riemann_mdm", "tangent_lr"),
        plots=plots,
    )
    return result


def freeze_heldout(
    root: Path,
    config: Path,
    development: Path,
    output: Path,
    verification: Path,
    cache: Path = Path("data/derived/decoding-trials"),
) -> dict[str, Any]:
    protocol, initial = read_protocol(config)
    if output.exists() or output.with_suffix(".sha256").exists():
        raise FileExistsError("A held-out freeze cannot be overwritten")
    required = ("within-subject", "cross-subject", "adaptation", "nulls")
    checksums = {}
    development_fingerprints = []
    if (development / "final-selection").exists():
        raise FileExistsError("Development final-selection audit already exists")
    for name in required:
        path = development / name / "manifest.json"
        if not path.is_file():
            raise ValueError(f"Development evaluation must finish first: {name}")
        info = json.loads(path.read_text())
        if (
            info["parameters"]["protocol_sha256"] != initial
            or info["parameters"].get("software") != identity()
        ):
            raise ValueError("Development protocol identity mismatch")
        if name != "nulls":
            if json.loads((path.parent / "failures.json").read_text()):
                raise ValueError("Resolve failed development cells before prospective freezing")
            development_fingerprints.append(info["source"]["trial_dataset_fingerprint"])
        else:
            development_fingerprints.append(info["source"]["dataset_fingerprint"])
            null_scores = pd.read_csv(path.parent / "null_scores.csv")
            for model in protocol["null_models"]:
                tested = null_scores[null_scores.model == model]
                if (
                    tested.permutation.nunique() != protocol["null_repetitions"]
                    or tested.failed_folds.ne(0).any()
                ):
                    raise ValueError("All prespecified nested null refits must finish")
        checksums[str(path)] = sha256(path)
    checked = json.loads(verification.read_text())
    if checked["status"] != "passed" or checked["software"] != identity():
        raise ValueError("Current code/environment lacks a passing verification receipt")
    dataset, _ = load_trials(root, tuple(protocol["development_subjects"]), protocol, cache)
    if any(value != dataset.fingerprint for value in development_fingerprints):
        raise ValueError("Development evaluations must use the exact full frozen training data")
    bank = build_bank(dataset, covariance_parameters(protocol))
    audit, selected, scores = FitAudit(), {}, []
    training = np.arange(len(dataset.y), dtype=np.int64)
    for model in protocol["models"]:
        params, candidates = choose_parameters(
            bank, model, protocol, training, np.array([], dtype=np.int64), audit
        )
        selected[model] = params
        scores.extend(candidates)
    frozen = {
        "protocol": protocol,
        "initial_protocol_sha256": initial,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "software": identity(),
        "development_dataset_fingerprint": dataset.fingerprint,
        "development_manifest_checksums": checksums,
        "verification_sha256": sha256(verification),
        "selection_rule": "subject-balanced development CV maximum; first-entry ties",
        "selected_parameters": selected,
        "selection_scores": scores,
        "heldout_accessed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(frozen, sort_keys=False))
    output.with_suffix(".sha256").write_text(digest(frozen) + "\n")
    (development / "final-selection").mkdir(exist_ok=False)
    audit.save(development / "final-selection")
    return {
        "status": "frozen",
        "output": str(output),
        "checksum": digest(frozen),
        "parameters": selected,
    }


def evaluate_heldout(
    root: Path,
    config: Path,
    subjects: tuple[int, ...],
    output: Path,
    *,
    fetch_data: bool = False,
    cache: Path = Path("data/derived/decoding-trials"),
    plots: bool = True,
) -> dict[str, Any]:
    frozen, checksum = read_protocol(config)
    if (
        "selected_parameters" not in frozen
        or frozen.get("heldout_accessed") is not False
        or frozen["software"] != identity()
    ):
        raise ValueError(
            "Explicit held-out evaluation requires matching frozen code and selection rules"
        )
    protocol = frozen["protocol"]
    if tuple(subjects) != tuple(protocol["heldout_subjects"]):
        raise ValueError("Prospective evaluation must use the frozen 36–65 cohort")
    if output.exists():
        raise FileExistsError(output)
    # Revalidate development training inputs before touching any held-out recording.
    development, dev_records = load_trials(
        root, tuple(protocol["development_subjects"]), protocol, cache
    )
    if development.fingerprint != frozen["development_dataset_fingerprint"]:
        raise ValueError("Development training data changed after freeze")
    output.mkdir(parents=True)
    atomic_json(
        output / "access_started.json",
        {
            "frozen_protocol_sha256": checksum,
            "frozen_at_utc": frozen["frozen_at_utc"],
            "access_started_utc": datetime.now(UTC).isoformat(),
            "software": identity(),
            "development_verified": True,
            "meaning": "prospective access; deterministic reruns are reproductions",
        },
    )
    if fetch_data:
        fetch(root, list(subjects), protocol["runs"])
    heldout, test_records = load_trials(
        root, subjects, protocol, cache, heldout=True, frozen_config=config
    )
    combined = combine_trials((development, heldout))
    bank = build_bank(combined, covariance_parameters(protocol))
    params = frozen["selected_parameters"]
    result = evaluate(
        bank,
        protocol,
        "cross-subject",
        output / "cross-subject",
        frozen_params=params,
        training_subjects=tuple(protocol["development_subjects"]),
        plots=plots,
    )
    adapted = adaptation(
        bank,
        protocol,
        output / "adaptation",
        frozen_params=params,
        training_subjects=tuple(protocol["development_subjects"]),
        plots=plots,
    )
    # Training inside each held-out subject is a distinct, explicitly labeled mode.
    del bank, combined, development
    within = evaluate(
        build_bank(heldout, covariance_parameters(protocol)),
        protocol,
        "within-subject",
        output / "within-subject",
        plots=plots,
    )
    atomic_json(
        output / "record_coverage.json", {"development": dev_records, "heldout": test_records}
    )
    atomic_json(
        output / "heldout_receipt.json",
        {
            "frozen_protocol_sha256": checksum,
            "frozen_at_utc": frozen["frozen_at_utc"],
            "evaluation_completed_utc": datetime.now(UTC).isoformat(),
            "model_selection_after_heldout": False,
            "mode_statuses": {
                "cross-subject": result["status"],
                "adaptation": adapted["status"],
                "within-subject": within["status"],
            },
            "software": identity(),
        },
    )
    statuses = {
        "cross-subject": result["status"],
        "adaptation": adapted["status"],
        "within-subject": within["status"],
    }
    return {
        "status": "complete" if all(s == "complete" for s in statuses.values()) else "partial",
        "mode_statuses": statuses,
        "output": str(output),
        "frozen_protocol_sha256": checksum,
    }


def development_suite(root: Path, config: Path, output: Path, plots: bool = True) -> dict[str, Any]:
    protocol, _ = read_protocol(config)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    dataset, records = load_trials(root, tuple(protocol["development_subjects"]), protocol)
    atomic_json(output / "record_coverage.json", records)
    dataset.metadata.to_csv(output / "trials.csv", index=False)
    bank = build_bank(dataset, covariance_parameters(protocol))
    results = [
        evaluate(bank, protocol, mode, output / mode, plots=plots)
        for mode in ("within-subject", "cross-subject")
    ]
    results.append(adaptation(bank, protocol, output / "adaptation", plots=plots))
    results.append(run_nulls(bank, protocol, output / "nulls"))
    atomic_json(output / "record_coverage.json", records)
    dataset.metadata.to_csv(output / "trials.csv", index=False)
    atomic_json(
        output / "suite.json", {"results": results, "wall_seconds": time.perf_counter() - started}
    )
    return {
        "status": "complete" if all(r["status"] == "complete" for r in results) else "partial",
        "output": str(output),
        "results": results,
    }
