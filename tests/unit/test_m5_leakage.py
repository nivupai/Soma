from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from typer.testing import CliRunner

from soma.cli import app
from soma.decoding.config import read_protocol
from soma.decoding.csp import TrainingCSP
from soma.decoding.data import combine_trials, load_trials
from soma.decoding.evaluation import FitAudit, choose_parameters, fit_fold
from soma.decoding.features import build_bank
from soma.decoding.models import make_pipeline, require_unfitted
from soma.decoding.riemannian import TrainingTangentSpace
from soma.decoding.splits import Fold, inner_splits, outer_splits, validate_split
from soma.decoding.synthetic import simulate_decoding


@pytest.fixture
def data():
    return simulate_decoding(n_subjects=4, n_trials=6)[0]


@pytest.fixture
def protocol():
    values, _ = read_protocol(Path("configs/decoding.yaml"))
    values["outer_subject_folds"] = 2
    values["inner_subject_folds"] = 2
    values["n_resamples"] = 199
    return values


def test_grouped_splits_and_every_trial_evaluated_once(data):
    for mode, count in [("within-subject", 12), ("cross-subject", 2)]:
        folds = outer_splits(data, mode, 2)
        assert len(folds) == count
        test = np.concatenate([f.test for f in folds])
        np.testing.assert_array_equal(np.sort(test), np.arange(len(data.y)))
        for fold in folds:
            receipt = validate_split(data, fold)
            assert not set(receipt["train"]) & set(receipt["test"])
            if mode == "cross-subject":
                assert not set(receipt["train_subjects"]) & set(receipt["test_subjects"])
                for inner in inner_splits(data, fold.train, 2):
                    assert not np.intersect1d(inner.train, fold.test).size
                    assert not np.intersect1d(inner.test, fold.test).size


def test_cross_subject_overlap_rejected(data):
    with pytest.raises(ValueError, match="participant overlap"):
        validate_split(data, Fold("leak", np.array([0, 1]), np.array([2, 3]), "cross-subject"))


def test_within_run_overlap_rejected(data):
    with pytest.raises(ValueError, match="training runs|run overlaps"):
        validate_split(data, Fold("leak", np.array([0, 1]), np.array([2, 3]), "within-subject"))


def test_duplicate_rows_and_event_windows_rejected(data):
    metadata = data.metadata.copy()
    metadata.loc[1, ["start_sample", "stop_sample"]] = metadata.loc[
        0, ["start_sample", "stop_sample"]
    ]
    with pytest.raises(ValueError, match="overlapping"):
        replace(data, metadata=metadata)
    metadata = data.metadata.copy()
    metadata.loc[1, "trial_id"] = metadata.loc[0, "trial_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        replace(data, metadata=metadata)


def test_missing_provenance_and_mixed_fingerprints_rejected(data):
    with pytest.raises(ValueError, match="provenance"):
        replace(data, metadata=data.metadata.drop(columns="event_id"))
    metadata = data.metadata.copy()
    metadata.loc[0, "preprocessing_fingerprint"] = "test-fitted-reference"
    with pytest.raises(ValueError, match="provenance"):
        replace(data, metadata=metadata)


def test_incompatible_channel_order_not_silently_combined(data):
    other = data.subset(np.flatnonzero(data.metadata.subject == 2))
    first = data.subset(np.flatnonzero(data.metadata.subject == 1))
    with pytest.raises(ValueError, match="channel order"):
        combine_trials((first, replace(other, channels=tuple(reversed(other.channels)))))


@pytest.mark.parametrize("kind", ["csp", "tangent", "scale"])
def test_global_prefitted_transform_rejected(data, kind):
    if kind == "csp":
        transformer = TrainingCSP(2).fit(data.X, data.y)
    elif kind == "tangent":
        transformer = TrainingTangentSpace().fit(np.stack([np.eye(3), np.eye(3) * 2]))
    else:
        transformer = StandardScaler().fit(data.X.reshape(len(data.y), -1))
    with pytest.raises(ValueError, match="Prefitted"):
        require_unfitted(Pipeline([("global_transform", transformer)]))


def test_outer_test_hyperparameter_selection_rejected(data, protocol):
    bank = build_bank(data)
    fold = outer_splits(data, "cross-subject", 2)[0]
    with pytest.raises(ValueError, match="Outer test"):
        choose_parameters(
            bank, "multiband_lr", protocol, np.r_[fold.train, fold.test[:1]], fold.test, FitAudit()
        )


def test_training_scaler_and_tangent_ignore_extreme_test_values(data, protocol):
    fold = outer_splits(data, "cross-subject", 2)[0]
    bank = build_bank(data)
    audit = FitAudit()
    model, _, _, _ = fit_fold(bank, "multiband_lr", protocol, fold, {}, audit, phase="outer")
    expected = bank.input("multiband_lr")[fold.train].mean(axis=0)
    np.testing.assert_allclose(model.named_steps["scale"].mean_, expected)
    reference = model.named_steps["scale"].mean_.copy()
    model.predict(bank.input("multiband_lr")[fold.test] * 1e5)
    np.testing.assert_array_equal(reference, model.named_steps["scale"].mean_)
    assert set(audit.partitions[next(iter(audit.partitions))]["train_subjects"]).isdisjoint(
        data.metadata.iloc[fold.test].subject
    )


def test_burst_thresholds_are_training_only(data, protocol):
    bank = build_bank(data)
    fold = outer_splits(data, "cross-subject", 2)[0]
    model, _, _, _ = fit_fold(bank, "burst_lr", protocol, fold, {}, FitAudit(), phase="outer")
    threshold = model.named_steps["bursts"].threshold_reference_.copy()
    model.predict(bank.burst_contexts[fold.test] * 100)
    np.testing.assert_array_equal(threshold, model.named_steps["bursts"].threshold_reference_)
    expected = np.median(bank.burst_contexts[fold.train, :, :, 1, 160:480], axis=(0, 3))
    np.testing.assert_allclose(threshold, expected)


def test_adaptation_cannot_use_evaluation_run_labels(data):
    target = np.flatnonzero(data.metadata.subject == 1)
    with pytest.raises(ValueError, match="Adaptation"):
        validate_split(data, Fold("leak", target[:8], target[8:], "adaptation"))


def test_reserved_heldout_loader_and_cli_gate(tmp_path, protocol):
    with pytest.raises(ValueError, match="Reserved"):
        load_trials(tmp_path, (36,), protocol, cache=tmp_path / "cache")
    with pytest.raises(ValueError, match="frozen"):
        load_trials(tmp_path, (36,), protocol, cache=tmp_path / "cache", heldout=True)
    result = CliRunner().invoke(
        app,
        [
            "decode",
            "evaluate-heldout",
            "--config",
            "configs/decoding.yaml",
            "--output",
            str(tmp_path / "heldout"),
        ],
    )
    assert result.exit_code == 1
    assert not (tmp_path / "heldout").exists()


@pytest.mark.parametrize(
    "name",
    [
        "within-subject",
        "cross-subject",
        "adaptation",
        "synthetic",
        "development-suite",
        "freeze-heldout",
        "evaluate-heldout",
    ],
)
def test_decode_cli_help(name):
    assert CliRunner().invoke(app, ["decode", name, "--help"]).exit_code == 0


def test_matched_run_comparisons_do_not_change_when_another_run_is_missing(protocol):
    import pandas as pd

    from soma.decoding.metrics import compare_models

    rows = []
    for subject in (1, 2):
        for model, run, value in [
            ("tangent_lr", 4, 0.9),
            ("multiband_lr", 4, 0.4),
            ("tangent_lr", 8, 0.0),
        ]:
            rows.append(
                dict(
                    subject=subject,
                    model=model,
                    run=run,
                    balanced_accuracy=value,
                    calibration_trials=0,
                )
            )
    table, _ = compare_models(pd.DataFrame(rows), protocol)
    assert table.iloc[0].estimate == pytest.approx(0.5)
    assert table.iloc[0].n_matched_subjects == 2


def test_all_failed_adaptation_is_preserved(tmp_path, data, protocol):
    from soma.decoding.evaluation import adaptation

    protocol["adaptation_trial_counts"] = [1000]
    bank = build_bank(data)
    result = adaptation(bank, protocol, tmp_path / "failed", plots=False)
    assert result["status"] == "failed"
    assert (tmp_path / "failed/failures.json").is_file()
    assert (tmp_path / "failed/partitions.json").is_file()


def test_outer_labels_do_not_select_hyperparameters(data, protocol):
    bank = build_bank(data)
    fold = outer_splits(data, "cross-subject", 2)[0]
    first, candidates = choose_parameters(
        bank, "multiband_lr", protocol, fold.train, fold.test, FitAudit()
    )
    altered = data.y.copy()
    altered[fold.test] = 1 - altered[fold.test]
    second, changed = choose_parameters(
        bank, "multiband_lr", protocol, fold.train, fold.test, FitAudit(), labels=altered
    )
    assert first == second
    assert candidates == changed


def test_trial_local_covariance_cache_preserves_predictions(data, protocol):
    bank = build_bank(data)
    fold = outer_splits(data, "cross-subject", 2)[0]
    raw = make_pipeline("tangent_lr", protocol)
    raw.fit(data.X[fold.train], data.y[fold.train])
    cached, pred, score, _ = fit_fold(
        bank, "tangent_lr", protocol, fold, {}, FitAudit(), phase="outer"
    )
    np.testing.assert_array_equal(pred, raw.predict(data.X[fold.test]))
    np.testing.assert_allclose(score, raw.decision_function(data.X[fold.test]), atol=1e-12)
    np.testing.assert_allclose(
        cached.named_steps["tangent"].reference_, raw.named_steps["tangent"].reference_, atol=1e-12
    )


def test_missing_run_is_not_replaced_with_single_run_training(data):
    restricted = data.subset(np.flatnonzero(data.metadata.run != 12))
    folds = outer_splits(restricted, "within-subject")
    assert len(folds) == 12
    for fold in folds:
        with pytest.raises(ValueError):
            validate_split(restricted, fold)


def test_subject_signature_fixture_exposes_random_trial_split_optimism():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import train_test_split

    # Idealized subject-specific signal fingerprints, labels unrelated to transferable physiology.
    subject = np.repeat(np.arange(8), 20)
    signals = np.eye(8)[subject]
    labels = subject % 2
    train, test = train_test_split(
        np.arange(len(labels)), test_size=0.3, random_state=42, stratify=labels
    )
    leaked = LogisticRegression(C=1000).fit(signals[train], labels[train])
    assert balanced_accuracy_score(labels[test], leaked.predict(signals[test])) == 1
    grouped_train, grouped_test = subject < 6, subject >= 6
    grouped = LogisticRegression(C=1000).fit(signals[grouped_train], labels[grouped_train])
    assert (
        balanced_accuracy_score(labels[grouped_test], grouped.predict(signals[grouped_test])) == 0.5
    )
