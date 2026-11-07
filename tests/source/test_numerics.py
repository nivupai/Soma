import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.source.inverse import Tikhonov
from soma.source.noise import NoiseModel, average_projector
from soma.source.power import band_powers
from soma.source.resolution import Resolution, spatial_metrics


@pytest.mark.parametrize("lambda2", [0.0, 0.1, 1.0, 1e12])
def test_identity_and_diagonal(lambda2):
    y = np.array([1.0, 2, 3])
    assert_allclose(Tikhonov(np.eye(3), lambda2).solve(y), y / (1 + lambda2))
    diagonal = np.array([1.0, 2, 4])
    expected = y / diagonal if lambda2 == 0 else diagonal / (diagonal**2 + lambda2) * y
    assert_allclose(Tikhonov(np.diag(diagonal), lambda2).solve(y), expected)


@pytest.mark.parametrize("shape", [(8, 3), (3, 8)])
def test_rectangular_noiseless(shape):
    lead = np.random.default_rng(1).normal(size=shape)
    truth = np.arange(shape[1], dtype=float)
    y = lead @ truth
    estimate = Tikhonov(lead, 0).solve(y)
    assert_allclose(lead @ estimate, y, atol=1e-13)
    if shape[0] > shape[1]:
        assert_allclose(estimate, truth, atol=1e-13)
    else:
        assert np.linalg.norm(estimate - truth) > 0.1
        assert np.linalg.norm(estimate) <= np.linalg.norm(truth)


def test_rank_deficient_ill_conditioned_and_limits():
    lead = np.diag([1.0, 1e-8, 0])
    y = np.array([1.0, 1e-8, 0])
    assert_allclose(Tikhonov(lead, 0).solve(y), [1, 1, 0])
    regularized = Tikhonov(lead, 1e-4)
    assert np.linalg.norm(regularized.kernel, 2) < 1.01
    assert np.linalg.norm(Tikhonov(lead, 0).kernel, 2) == 1e8
    assert np.linalg.norm(Tikhonov(lead, 1e14).solve(y)) < 1e-13
    assert regularized.diagnostics(y, np.ones(3))["relative_source_error"] > 0.5


def test_noise_whitening_reference_rank_and_order():
    rng = np.random.default_rng(3)
    p = average_projector(5)
    a = rng.normal(size=(5, 5))
    x = a @ rng.normal(size=(5, 10000))
    noise = NoiseModel.estimate(x, tuple("abcde"), p)
    assert noise.rank == 4
    assert_allclose(noise.whitener @ noise.covariance @ noise.whitener.T, np.eye(4), atol=1e-13)
    assert_allclose(noise.covariance @ np.ones(5), np.zeros(5), atol=1e-13)
    with pytest.raises(ValueError):
        noise.require(tuple("bacde"), p)
    with pytest.raises(ValueError):
        noise.require(tuple("abcde"), np.eye(5))
    noise.require(tuple("abcde"), p)
    assert noise.diagnostics()["whitening_identity_error"] < 1e-12


@pytest.mark.parametrize(
    "c",
    [
        np.diag([1.0, -1]),
        np.zeros((2, 2)),
        np.array([[1.0, 0.3], [0.2, 1]]),
        np.full((2, 2), np.nan),
    ],
)
def test_invalid_covariances(c):
    with pytest.raises(ValueError):
        NoiseModel(c, ("a", "b"), np.eye(2))


def test_projector_validation_and_ssp_rank():
    p = np.diag([1.0, 1, 0])
    noise = NoiseModel.estimate(np.random.default_rng(0).normal(size=(3, 1000)), ("a", "b", "c"), p)
    assert noise.rank == 2
    with pytest.raises(ValueError):
        NoiseModel(np.eye(3), ("a", "b", "c"), p)
    with pytest.raises(ValueError):
        NoiseModel.estimate(np.ones((3, 10)), ("a", "b", "c"), p * 0.8)


def test_correlated_noise_and_misestimation():
    rng = np.random.default_rng(123)
    lead = rng.normal(size=(7, 3))
    c = np.diag([0.001, 0.002, 0.003, 5, 8, 10, 20])
    noise = NoiseModel(c, tuple("abcdefg"), np.eye(7))
    j = rng.normal(size=(3, 2000))
    y = lead @ j + np.linalg.cholesky(c) @ rng.normal(size=(7, 2000))
    good = Tikhonov(lead, 0.1, noise)
    bad = Tikhonov(lead, 0.1)
    assert np.linalg.norm(good.solve(y) - j) < 0.1 * np.linalg.norm(bad.solve(y) - j)
    # Weighted normal-equation solution is an independent analytical oracle.
    expected = np.linalg.solve(
        lead.T @ np.linalg.solve(c, lead) + 0.1 * np.eye(3), lead.T @ np.linalg.solve(c, y)
    )
    assert_allclose(good.solve(y), expected, atol=1e-12)


def test_mismatch_and_noise_amplification():
    lead = np.diag([1.0, 0.001])
    truth = np.ones(2)
    y = lead @ truth + [0.0, 0.01]
    assert np.linalg.norm(Tikhonov(lead, 0.01).solve(y) - truth) < np.linalg.norm(
        Tikhonov(lead, 0).solve(y) - truth
    )
    assert np.linalg.norm(Tikhonov(lead * 2, 0).solve(lead @ truth) - truth) > 0.5


def test_resolution_psf_ctf_and_non_linear_guard():
    lead = np.array([[1.0, 2, 0], [0, 1, 1]])
    w = Tikhonov(lead, 0.1).kernel
    res = Resolution(w, lead)
    explicit = w @ lead
    assert_allclose(res.psf([0, 2]), explicit[:, [0, 2]])
    assert_allclose(res.ctf([0, 2]), explicit[[0, 2]])
    assert_allclose(res.diagonal, np.diag(explicit))
    assert_allclose(res.apply(np.ones(3)), explicit @ np.ones(3))
    with pytest.raises(ValueError):
        Resolution(w, lead, linear=False)
    with pytest.raises(ValueError):
        res.psf(list(range(129)))
    xyz = np.array([[0.0, 0, 0], [0.01, 0, 0], [0.03, 0, 0]])
    m = spatial_metrics(np.array([0.0, 2, 0]), 0, xyz, np.array([0.0, 0.02, np.inf]))
    assert m["peak_euclidean_m"] == 0.01
    assert m["peak_geodesic_m"] == 0.02
    assert m["off_target_energy_fraction"] == 1


def test_free_fixed_orientation_algebra():
    rng = np.random.default_rng(1)
    free = rng.normal(size=(6, 9))
    fixed = free[:, 2::3]
    j = rng.normal(size=(3, 20))
    j_free = np.zeros((3, 3, 20))
    j_free[:, 2] = j
    assert_allclose(free @ j_free.reshape(9, 20), fixed @ j)
    assert Tikhonov(free, 0.1).kernel.shape == (9, 6)
    assert Tikhonov(fixed, 0.1).kernel.shape == (3, 6)


def test_induced_trial_power_survives_phase_cancellation():
    t = np.arange(320) / 160
    trials = np.array([np.sin(2 * np.pi * 10 * t), -np.sin(2 * np.pi * 10 * t)])
    trial_power = band_powers(trials, 160)["mu"].mean()
    evoked_power = band_powers(trials.mean(axis=0, keepdims=True), 160)["mu"][0]
    assert_allclose(trial_power, 0.5, atol=1e-12)
    assert evoked_power == 0
    from soma.core.signal import Signal
    from soma.signal.spectral import WelchConfig, welch

    for row in trials:
        old = welch(Signal(row, 160), WelchConfig(nperseg=160, noverlap=80))
        assert_allclose(band_powers(row[None], 160)["mu"][0], old.band_power(8, 13), atol=1e-12)


def test_batched_power_interpolates_noninteger_grid():
    from soma.core.signal import Signal
    from soma.signal.spectral import WelchConfig, welch

    fs = 159.5
    row = np.random.default_rng(0).normal(size=319)
    old = welch(Signal(row, fs), WelchConfig(nperseg=int(fs), noverlap=int(fs / 2)))
    powers = band_powers(row[None], fs)
    assert_allclose(powers["mu"][0], old.band_power(8, 13), rtol=1e-12)
    assert_allclose(powers["beta"][0], old.band_power(13, 30), rtol=1e-12)
    with pytest.raises(ValueError):
        band_powers(row[None], 50)
