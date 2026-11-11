"""Train/test boundary tests and independent numerical references."""

import copy
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
from scipy.signal import welch as scipy_welch
from sklearn.metrics import balanced_accuracy_score, confusion_matrix

from soma.core.signal import Signal
from soma.decoding.covariance import TrialCovariances
from soma.decoding.evaluation import FitAudit, fit_fold
from soma.decoding.metrics import classification_metrics
from soma.eeg_benchmark.evaluation import bank, evaluate, folds, select
from soma.eeg_benchmark.protocol import benchmark_protocol, design, inspect_protocol
from soma.eeg_benchmark.statistics import (
    bootstrap,
    null_diagnostic,
    permuted_labels,
    subject_table,
    summarize,
)
from soma.signal.spectral import WelchConfig, welch
from soma.workflow.model import digest


def test_protocol_sealed_scope_and_schema():
    p = design(4, 2)
    sealed = benchmark_protocol(p, digest({"fictional": True}))
    assert inspect_protocol(sealed) == p
    assert not sealed.protocol.document()["scientific"]["inference"]["confirmatory_claim_allowed"]
    bad = copy.deepcopy(p)
    bad["labels"] = {"T1": 1, "T2": 0}
    with pytest.raises(ValueError):
        benchmark_protocol(bad, digest({}))


@pytest.mark.parametrize(
    "field",
    ["runs", "models", "labels", "search", "missing_policy", "exchangeability_attested", "history"],
)
def test_protocol_amendments_cannot_be_silent(field):
    p = design(4, 2)
    p[field] = "changed"
    with pytest.raises(ValueError):
        benchmark_protocol(p, digest({}))


def test_grouped_outer_folds_and_fair_target_trials(synthetic):
    d, p, _ = synthetic
    within = folds(d, p, [1, 2, 3, 4], [5, 6], "within-subject")
    cross = folds(d, p, [1, 2, 3, 4], [5, 6], "cross-subject")
    assert len(within) == 6 and len(cross) == 1
    assert set(np.concatenate([f.test for f in within])) == set(cross[0].test)
    for f in within:
        assert not set(d.metadata.iloc[f.train].run) & set(d.metadata.iloc[f.test].run)
    assert not set(d.metadata.iloc[cross[0].train].subject) & set(
        d.metadata.iloc[cross[0].test].subject
    )
    with pytest.raises(ValueError):
        folds(d, p, [1, 2, 5], [5, 6], "cross-subject")


@pytest.mark.parametrize("model", ["multiband_lr", "csp_lda", "riemann_mdm", "tangent_lr"])
def test_heldout_perturbation_cannot_change_training_state(synthetic, model):
    d, p, b = synthetic
    f = folds(d, p, [1, 2, 3, 4], [5, 6], "cross-subject")[0]
    first, _, _, _ = fit_fold(b, model, p, f, {}, FitAudit(), phase="outer")
    X = d.X.copy()
    X[f.test] *= 100
    altered = replace(d, X=X, context=d.context.copy())
    other = bank(altered, p)
    second, _, _, _ = fit_fold(other, model, p, f, {}, FitAudit(), phase="outer")
    if model == "csp_lda":
        np.testing.assert_allclose(first["csp"].filters_, second["csp"].filters_, rtol=0, atol=0)
    elif model == "tangent_lr":
        np.testing.assert_array_equal(first["tangent"].reference_, second["tangent"].reference_)
    elif model == "multiband_lr":
        np.testing.assert_array_equal(first["scale"].mean_, second["scale"].mean_)
    else:
        np.testing.assert_array_equal(
            first["classifier"].model_.covmeans_, second["classifier"].model_.covmeans_
        )


def test_source_only_selection_partitions(synthetic):
    _, p, b = synthetic
    chosen, audit, tried = select(b, p, [1, 2, 3, 4], [5, 6])
    assert len(chosen) == 4 and tried
    assert all(
        not {5, 6} & set(r["train_subjects"] + r["test_subjects"])
        for r in audit.partitions.values()
    )
    with pytest.raises(ValueError):
        select(b, p, [1, 2, 5], [5, 6])


def test_metrics_match_sklearn():
    y = np.array([0, 0, 0, 1, 1])
    pred = np.array([0, 1, 0, 0, 1])
    r = classification_metrics(y, pred)
    assert r["balanced_accuracy"] == balanced_accuracy_score(y, pred)
    np.testing.assert_array_equal(
        [[r["tn"], r["fp"]], [r["fn"], r["tp"]]], confusion_matrix(y, pred)
    )
    assert r["specificity"] == pytest.approx(2 / 3) and r["sensitivity"] == 0.5


def test_volts_PSD_and_power_match_independent_scipy():
    fs = 160.0
    t = np.arange(640) / fs
    x = 20e-6 * np.sin(2 * np.pi * 10 * t)
    s = welch(Signal(x, fs, "C3"), WelchConfig(160, 80))
    f, p = scipy_welch(x, fs=fs, nperseg=160, noverlap=80, detrend="constant", scaling="density")
    np.testing.assert_allclose(s.density, p, atol=1e-25, rtol=1e-12)
    assert s.band_power(8, 13) == pytest.approx((20e-6) ** 2 / 2, rel=1e-10)
    assert s.metadata["units"] == "V^2/Hz"


def test_trial_local_covariance_matches_sklearn(synthetic):
    from sklearn.covariance import OAS

    d, _, _ = synthetic
    c = TrialCovariances(relative_floor=0).fit_transform(d.X[:2])
    for i in range(2):
        np.testing.assert_allclose(
            c[i], OAS().fit(d.X[i].T * 1e6).covariance_, rtol=1e-12, atol=1e-12
        )


def test_permutations_preserve_groups_and_no_nominal_human_p(synthetic):
    d, _, _ = synthetic
    y = permuted_labels(d.y, d.metadata, 1)
    for ix in d.metadata.groupby(["subject", "run"]).indices.values():
        assert sorted(y[ix]) == sorted(d.y[ix])
    r = null_diagnostic(0.65, [0.49, 0.5, 0.51])
    assert r["p_value"] is None and not r["exchangeability_attested"]
    assert r["monte_carlo_exceedance_interval"][0] == 0


def test_uncertainty_uses_subjects_not_trials():
    r = bootstrap([0.4, 0.6, 0.8], resamples=1999)
    assert r["unit"] == "subject" and r["n_subjects"] == 3 and r["mean"] == pytest.approx(0.6)
    with pytest.raises(ValueError):
        bootstrap(np.ones((3, 20)))


def test_missing_results_and_corrupted_cells_retained(synthetic, tmp_path):
    _, p, b = synthetic
    chosen, _, _ = select(b, p, [1, 2, 3, 4], [5, 6])
    rows, cells, _ = evaluate(b, p, [1, 2, 3, 4], [5, 6], chosen, tmp_path, "a" * 64)
    assert len(cells) == 35 and all(c["status"] == "COMPLETE" for c in cells)
    scores = subject_table(rows, [5, 6, 7], p["evaluation_runs"])
    summary = summarize(scores, p)
    assert all(
        r["planned_subjects"] == 3 and r["missing_subjects"] == 1 for r in summary["methods"]
    )
    path = next((tmp_path / "cells").glob("*/result.json"))
    path.write_text("{}")
    with pytest.raises(ValueError):
        evaluate(b, p, [1, 2, 3, 4], [5, 6], chosen, tmp_path, "a" * 64)


def test_adaptation_uses_separate_run_and_same_test_trials(synthetic):
    from soma.eeg_benchmark.evaluation import adaptation

    _, p, b = synthetic
    chosen, _, _ = select(b, p, [1, 2, 3, 4], [5, 6])
    pred, cells, _ = adaptation(b, p, [1, 2, 3, 4], [5, 6], chosen)
    assert len(cells) == 12
    for subject in (5, 6):
        matched = [
            set(c["test_trial_ids"])
            for c in cells
            if c["subject"] == subject and c["status"] == "COMPLETE"
        ]
        assert all(s == matched[0] for s in matched)
    assert not pred.run.eq(4).any()


def test_verified_record_cache_has_real_input_binding(synthetic, tmp_path):
    from soma.core.provenance import sha256
    from soma.eeg_benchmark.data import record_graph
    from soma.human.model import pseudonym
    from soma.human.permissions import evidence
    from soma.workflow.runtime import Executor

    d, p, _ = synthetic
    folder = tmp_path / "raw/MNE-eegbci-data/files/eegmmidb/1.0.0/S001"
    folder.mkdir(parents=True)
    file = folder / "S001R04.edf"
    file.write_bytes(b"Fictional EDF transport fixture, not a real recording")
    notice = tmp_path / "notice.txt"
    notice.write_bytes(
        b"EEG Motor Movement/Imagery Open Data Commons Attribution License v1.0 synthetic fixture"
    )
    permission = evidence(
        "eegmmidb",
        "1.0.0",
        notice.read_bytes(),
        source="https://physionet.org/content/eegmmidb/1.0.0/",
        license="ODC-By-1.0",
        supported=True,
    )
    indices = np.flatnonzero((d.metadata.subject == 1) & (d.metadata.run == 4))
    c = {
        "root": str(tmp_path / "raw"),
        "subject": 1,
        "run": 4,
        "sha256": sha256(file),
        "subject_key": pseudonym("eegmmidb", "1", bytes(range(32))),
        "permission": permission.document(),
        "permission_source": str(notice),
    }
    graph, registry = record_graph(c, p)
    fake = (
        {"X": d.X[indices], "context": d.context[indices]},
        d.metadata.iloc[indices],
        {"proposals": [{"accepted": True}] * len(indices)},
    )
    with patch("soma.eeg_benchmark.data._record", return_value=fake):
        result = Executor(registry, tmp_path / "cache").run(
            graph, inputs={"record": c}, input_root=tmp_path / "raw"
        )
    assert result["status"] == "COMPLETE", result


@pytest.mark.parametrize("fault", ["labels", "predictions", "class"])
def test_invalid_class_or_label_data_rejected(synthetic, fault):
    d, p, b = synthetic
    if fault == "labels":
        with pytest.raises(ValueError):
            permuted_labels(np.ones(len(d.y)) * 3, d.metadata, 1)
    elif fault == "predictions":
        with pytest.raises(ValueError):
            classification_metrics([0, 1], [0])
    else:
        y = np.zeros_like(d.y)
        fold = folds(d, p, [1, 2, 3, 4], [5, 6], "cross-subject")[0]
        with pytest.raises(ValueError, match="class"):
            fit_fold(b, "multiband_lr", p, fold, {}, FitAudit(), phase="outer", labels=y)


def test_adaptation_contamination_is_rejected(synthetic):
    from soma.eeg_benchmark.evaluation import adaptation

    _, p, b = synthetic
    chosen, _, _ = select(b, p, [1, 2, 3, 4], [5, 6])
    bad = copy.deepcopy(p)
    bad["adaptation_test_runs"] = [4]
    _, cells, _ = adaptation(b, bad, [1, 2, 3, 4], [5, 6], chosen)
    assert all(c["status"] == "FAILED" for c in cells)


def test_frozen_evaluation_records_all_candidates(synthetic):
    _, p, b = synthetic
    _, _, tried = select(b, p, [1, 2, 3, 4], [5, 6])
    assert sum(r["model"] == "multiband_lr" for r in tried) == 2
    assert sum(r["model"] == "csp_lda" for r in tried) == 4


def test_class_qc_failure_preserves_trial_accounting(synthetic, tmp_path):
    import json

    from soma.core.provenance import sha256
    from soma.eeg_benchmark.data import load_dataset
    from soma.human.model import pseudonym
    from soma.human.permissions import evidence
    from soma.workflow.model import digest

    d, p, _ = synthetic
    root = tmp_path / "raw"
    records = []
    for subject in [1, 2]:
        for run in [4, 8, 12]:
            file = (
                root
                / f"MNE-eegbci-data/files/eegmmidb/1.0.0/S{subject:03}/S{subject:03}R{run:02}.edf"
            )
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"fictional transport")
            records.append(
                {
                    "subject": subject,
                    "run": run,
                    "subject_key": pseudonym("eegmmidb", str(subject), b"x" * 32),
                    "sha256": sha256(file),
                    "status": "AVAILABLE",
                }
            )
    inv = {
        "records": records,
        "fingerprint": digest(records),
        "source_subjects": [1],
        "target_subjects": [2],
    }
    notice = tmp_path / "notice.txt"
    notice.write_text("EEG Motor Movement/Imagery Open Data Commons Attribution License v1.0")
    permission = evidence(
        "eegmmidb",
        "1.0.0",
        notice.read_bytes(),
        source="https://physionet.org/content/eegmmidb/1.0.0/",
        license="ODC-By-1.0",
        supported=True,
    )

    def record(root, subject, run, p):
        ix = np.flatnonzero((d.metadata.subject == subject) & (d.metadata.run == run))
        if subject == 2:
            ix = ix[d.y[ix] == 0]
        return (
            {"X": d.X[ix], "context": d.context[ix]},
            d.metadata.iloc[ix],
            {"proposals": [{"accepted": True}] * 6},
        )

    coverage_path = tmp_path / "coverage.json"
    with patch("soma.eeg_benchmark.data._record", side_effect=record):
        result, coverage = load_dataset(
            root, inv, p, permission, notice, tmp_path / "cache", coverage_path
        )
    failed = [r for r in coverage if r["status"] == "FAILED"]
    assert len(failed) == 3
    assert all(r["n_proposed"] == 6 and r["n_accepted"] > 0 and r["decisions"] for r in failed)
    assert sum(r["n_proposed"] for r in coverage) == 36
    assert set(result.metadata.subject) == {1}
    assert len(json.loads(coverage_path.read_text())) == 6
