from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import balanced_accuracy_score

from soma.decoding.config import read_protocol
from soma.decoding.covariance import TrialCovariances
from soma.decoding.csp import TrainingCSP
from soma.decoding.data import validate_tensor
from soma.decoding.models import make_pipeline as decoder_pipeline
from soma.decoding.synthetic import simulate_decoding


def test_csp_known_mixing_directions_and_component_order():
    dataset, truth = simulate_decoding(
        n_subjects=2, n_trials=12, noise=0, subject_shift=0, run_drift=0
    )
    csp = TrainingCSP(2, reg=0, component_order="mutual_info").fit(dataset.X, dataset.y)
    mixing = np.asarray(truth["base_mixing"])
    directions = csp.filters_[:2] @ mixing
    chosen = np.argmax(np.abs(directions), axis=1)
    assert set(chosen) == {0, 1}
    for row, index in zip(directions, chosen, strict=True):
        other = np.delete(row, index)
        assert np.linalg.norm(other) < 1e-8 * abs(row[index])
    assert csp.transform(dataset.X).shape == (len(dataset.y), 2)
    alternate = TrainingCSP(2, reg=0, component_order="alternate").fit(dataset.X, dataset.y)
    assert set(np.argmax(np.abs(alternate.filters_[:2] @ mixing), axis=1)) == {0, 1}


@pytest.mark.parametrize("n_components", [2, 4])
def test_csp_rank_deficient_mixture_and_shape(n_components):
    dataset, _ = simulate_decoding(
        n_subjects=2, n_trials=8, rank_deficient=True, subject_shift=0, run_drift=0
    )
    csp = TrainingCSP(n_components, reg=0.1).fit(dataset.X, dataset.y)
    assert csp.training_rank_ == 8
    assert csp.transform(dataset.X).shape == (len(dataset.y), n_components)
    assert np.isfinite(csp.transform(dataset.X)).all()


def test_csp_nonfinite_zero_rank_and_too_many_components():
    x = np.ones((8, 3, 30))
    y = np.tile([0, 1], 4)
    with pytest.raises(ValueError, match="rank"):
        TrainingCSP(3).fit(x, y)
    x[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        TrainingCSP(2).fit(x, y)
    with pytest.raises(ValueError, match="Complex"):
        validate_tensor(np.ones((3, 2, 10), dtype=complex) * 1j)


def test_synthetic_determinism_unequal_counts_imbalance_and_null():
    first, _ = simulate_decoding(seed=20, n_subjects=3, n_trials=7, right_fraction=0.7)
    second, _ = simulate_decoding(seed=20, n_subjects=3, n_trials=7, right_fraction=0.7)
    np.testing.assert_array_equal(first.X, second.X)
    np.testing.assert_array_equal(first.y, second.y)
    assert first.metadata.groupby(["subject", "run"]).size().unique().tolist() == [7, 9, 11]
    assert np.mean(first.y) > 0.6
    null, _ = simulate_decoding(seed=20, n_subjects=3, n_trials=7, null=True)
    assert not np.array_equal(first.y, null.y)


def test_separated_covariance_classification_and_independent_label_null():
    scores, null_scores = [], []
    protocol, _ = read_protocol(Path("configs/decoding.yaml"))
    for seed in range(5):
        for null, destination in [(False, scores), (True, null_scores)]:
            data, _ = simulate_decoding(
                seed=seed,
                n_subjects=3,
                n_trials=24,
                effect=0.95,
                noise=0.1,
                subject_shift=0,
                run_drift=0,
                null=null,
            )
            train = data.metadata.subject.to_numpy() != 3
            test = ~train
            model = decoder_pipeline("tangent_lr", protocol)
            model.fit(data.X[train], data.y[train])
            destination.append(balanced_accuracy_score(data.y[test], model.predict(data.X[test])))
    # Five independent synthetic datasets; broad bounds, not every noisy fold.
    assert np.mean(scores) > 0.9
    assert 0.35 < np.mean(null_scores) < 0.65


def test_empirical_covariance_recovers_known_mixture_population():
    data, truth = simulate_decoding(
        seed=7, n_subjects=2, n_trials=60, noise=0, subject_shift=0, run_drift=0
    )
    covariances = TrialCovariances("empirical", relative_floor=0).fit_transform(data.X)
    inverse = np.asarray(truth["base_mixing"]).T
    recovered = inverse @ covariances @ inverse.T / (truth["scale_v"] * 1e6) ** 2
    for label in (0, 1):
        mean = recovered[data.y == label].mean(axis=0)
        target = np.full(9, 0.16)
        target[:2] = [1 + truth["effect"] * (2 * label - 1), 1 - truth["effect"] * (2 * label - 1)]
        np.testing.assert_allclose(mean, np.diag(target), atol=1e-12)
