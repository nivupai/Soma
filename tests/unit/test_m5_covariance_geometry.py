import numpy as np
import pytest

from soma.decoding.covariance import SymmetricVectorizer, TrialCovariances, diagnostics, require_spd
from soma.decoding.riemannian import TrainingTangentSpace, riemannian_distance, riemannian_mean


@pytest.mark.parametrize("estimator", ["empirical", "shrinkage", "oas", "ledoit_wolf"])
def test_covariance_symmetry_spd_and_scale_permutation(estimator):
    x = np.random.default_rng(13).normal(size=(8, 4, 160)) * 1e-6
    model = TrialCovariances(estimator=estimator)
    first = model.fit_transform(x)
    assert all(row["minimum_eigenvalue"] > 0 for row in diagnostics(first))
    np.testing.assert_allclose(first, first.transpose(0, 2, 1), atol=1e-13)
    np.testing.assert_allclose(
        TrialCovariances(estimator).fit_transform(x * 3), first * 9, rtol=1e-11, atol=1e-13
    )
    p = [2, 0, 3, 1]
    permuted = TrialCovariances(estimator).fit_transform(x[:, p])
    np.testing.assert_allclose(permuted, first[:, p][:, :, p], rtol=1e-10, atol=1e-13)
    normalized = TrialCovariances(estimator, trace_normalize=True).fit_transform(x)
    np.testing.assert_allclose(np.trace(normalized, axis1=1, axis2=2), 1)


def test_analytic_empirical_covariance_and_rank_floor():
    t = np.arange(320) / 160
    signals = np.stack([np.sqrt(2) * np.sin(2 * np.pi * f * t) for f in (10, 20, 30)])
    x = signals[None] * 1e-6
    cov = TrialCovariances("empirical", relative_floor=0).fit_transform(x)
    np.testing.assert_allclose(cov[0], np.eye(3), atol=1e-14)
    rank_def = np.concatenate([x, x[:, :1]], axis=1)
    singular = TrialCovariances("empirical", relative_floor=0).fit_transform(rank_def)
    with pytest.raises(ValueError, match="singular"):
        require_spd(singular)
    regularizer = TrialCovariances("empirical", relative_floor=1e-5)
    spd = regularizer.fit_transform(rank_def)
    assert regularizer.last_diagnostics_[0]["rank_before_floor"] == 3
    assert np.linalg.eigvalsh(spd).min() > 0
    assert np.linalg.cond(spd[0]) <= 2.1e5


@pytest.mark.parametrize(
    "kwargs", [dict(estimator="bad"), dict(relative_floor=-1), dict(shrinkage=2)]
)
def test_covariance_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        TrialCovariances(**kwargs).fit(np.ones((2, 3, 10)))


def test_zero_energy_and_nonfinite_covariances_fail():
    with pytest.raises(ValueError, match="Zero-energy"):
        TrialCovariances().fit_transform(np.zeros((2, 3, 10)))
    x = np.ones((2, 3, 10))
    x[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        TrialCovariances().fit(x)
    with pytest.raises(ValueError, match="symmetric"):
        diagnostics(np.array([[[1e-20, 1e-20], [0.0, 1e-20]]]))


def test_frobenius_vectorization_isometry():
    x = np.array([[[2.0, 0.2], [0.2, 3.0]], [[1.0, 0.1], [0.1, 2.0]]])
    features = SymmetricVectorizer().fit_transform(x)
    np.testing.assert_allclose(
        np.linalg.norm(features[0] - features[1]), np.linalg.norm(x[0] - x[1])
    )


def test_diagonal_distance_and_geometric_mean_known_answer():
    a, b = np.diag([1.0, 9.0]), np.diag([9.0, 1.0])
    assert riemannian_distance(a, b) == pytest.approx(np.sqrt(2) * np.log(9), abs=1e-12)
    mean = riemannian_mean(np.stack([a, b]))
    np.testing.assert_allclose(mean, np.eye(2) * 3, atol=1e-10)
    assert not np.allclose(mean, (a + b) / 2)


def test_affine_congruence_distance_properties():
    rng = np.random.default_rng(18)
    x, y, g = rng.normal(size=(3, 4, 4))
    a, b = x @ x.T + np.eye(4), y @ y.T + np.eye(4)
    g += np.eye(4) * 4
    distance = riemannian_distance(a, b)
    assert distance > 0
    assert riemannian_distance(a, a) < 1e-12
    assert riemannian_distance(b, a) == pytest.approx(distance, rel=1e-12)
    assert riemannian_distance(g @ a @ g.T, g @ b @ g.T) == pytest.approx(distance, rel=1e-10)


def test_ill_conditioned_diagonal_and_training_tangent_reference():
    a, b = np.diag([1e-10, 1.0]), np.diag([2e-10, 3.0])
    assert riemannian_distance(a, b) == pytest.approx(np.hypot(np.log(2), np.log(3)), rel=1e-10)
    training = np.stack([np.eye(3), np.eye(3) * 4])
    tangent = TrainingTangentSpace().fit(training)
    reference = tangent.reference_.copy()
    transformed = tangent.transform(np.eye(3)[None] * 100)
    assert transformed.shape == (1, 6)
    np.testing.assert_array_equal(tangent.reference_, reference)
    np.testing.assert_allclose(tangent.transform(reference[None]), 0, atol=1e-14)
    assert tangent.space_.tsupdate is False


def test_mdm_congruence_predictions_on_precomputed_covariances():
    from soma.decoding.riemannian import CovarianceMDM

    rng = np.random.default_rng(19)
    labels = np.tile([0, 1], 10)
    matrices = np.stack(
        [np.diag([1 + 3 * y, 4 - 3 * y, 2.0]) + 0.03 * rng.normal(size=(3, 3)) for y in labels]
    )
    matrices = (matrices + matrices.transpose(0, 2, 1)) / 2
    g = np.array([[2.0, 0.3, 0], [0, 1.0, 0.2], [0.1, 0, 1.5]])
    transformed = g @ matrices @ g.T
    first = CovarianceMDM("riemann").fit(matrices[:12], labels[:12])
    second = CovarianceMDM("riemann").fit(transformed[:12], labels[:12])
    np.testing.assert_array_equal(first.predict(matrices[12:]), second.predict(transformed[12:]))
