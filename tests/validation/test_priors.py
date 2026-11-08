"""Independent analytical, covariance, basis and source-order checks."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.source.noise import NoiseModel
from soma.source.priors import SourcePrior, fit_prior, make_prior, normalize_prior, vertex_areas


def noise(n):
    return NoiseModel(np.eye(n), tuple(map(str, range(n))), np.eye(n))


def test_analytical_diagonal_kernel_and_resolution():
    lead = np.diag([2.0, 3.0, 0.0])
    prior = SourcePrior(np.array([[[4.0]], [[0.5]], [[2.0]]]), ("a", "b", "c"), "MRI", "oracle", {})
    fit = fit_prior(lead, prior, noise(3), alpha=0.25, source_ids=prior.source_ids)
    expected = np.diag([8 / (16 + 0.25), 1.5 / (4.5 + 0.25), 0])
    assert_allclose(fit.kernel, expected, atol=1e-14)
    assert_allclose(fit.diagnostics["resolution_diagonal"], np.diag(expected) * [2, 3, 0])
    assert_allclose(fit.diagnostics["effective_complexity"], sum([16 / 16.25, 4.5 / 4.75]))


def test_low_rank_zero_regularization_observable_solution():
    lead = np.array([[1.0, 1.0], [2.0, 2.0]])
    p = SourcePrior(np.array([[[1.0]], [[0.0]]]), ("a", "b"), "MRI", "rank-deficient", {})
    inv = fit_prior(lead, p, noise(2), alpha=0, source_ids=p.source_ids)
    assert_allclose(inv.apply([3.0, 6.0]), [3.0, 0.0], atol=1e-12)
    assert_allclose(lead @ inv.apply([3.0, 6.0]), [3.0, 6.0])


def test_covariance_scale_and_ridge_scale_cancel():
    lead = np.array([[1.0, 2.0], [-1.0, 3.0]])
    p = make_prior(lead, ("a", "b"), orientation="fixed")
    q = SourcePrior(p.blocks * 7, p.source_ids, p.frame, p.policy, {})
    a = fit_prior(lead, p, noise(2), alpha=0.3, source_ids=p.source_ids)
    b = fit_prior(lead, q, noise(2), alpha=2.1, source_ids=p.source_ids)
    assert_allclose(a.kernel, b.kernel, rtol=1e-12)


@pytest.mark.parametrize("alpha", [1e-12, 0.1, 1e6])
def test_ridge_limits_independent_one_dimensional(alpha):
    p = make_prior([[2.0]], ("a",), orientation="fixed")
    inv = fit_prior([[2.0]], p, noise(1), alpha=alpha, source_ids=("a",))
    assert_allclose(inv.apply([3.0]), [6 / (4 + alpha)], rtol=1e-12)


@pytest.mark.parametrize(
    "bad", [np.array([[[-1.0]]]), np.array([[[0.0]]]), np.array([[[np.nan]]]), np.eye(2)[None]]
)
def test_invalid_covariance_rejected(bad):
    with pytest.raises(ValueError):
        SourcePrior(bad, ("a",), "MRI", "bad", {})


def test_asymmetric_covariance_rejected():
    b = np.eye(3)[None]
    b[0, 0, 1] = 0.1
    with pytest.raises(ValueError, match="symmetric"):
        SourcePrior(b, ("a",), "MRI", "bad", {})


@pytest.mark.parametrize(
    "ids,frame,columns", [(("b", "a"), "MRI", 2), (("a", "b"), "HEAD", 2), (("a", "b"), "MRI", 6)]
)
def test_identity_and_basis_rejected(ids, frame, columns):
    p = make_prior(np.eye(2), ("a", "b"), orientation="fixed")
    with pytest.raises(ValueError):
        p.require(ids, frame, columns)


def test_covariance_immutable():
    b = np.ones((1, 1, 1))
    p = SourcePrior(b, ("a",), "MRI", "test", {})
    b[:] = 2
    assert p.trace == 1
    with pytest.raises(ValueError):
        p.blocks[0, 0, 0] = 3


def test_orientation_block_and_rotation_equivariance():
    normal = np.array([[0.0, 0.0, 1.0]])
    lead = np.array([[1.0, 2.0, 3.0], [3.0, -2.0, 1.0], [1.0, 4.0, -1.0]])
    prior = make_prior(lead, ("a",), policy="orientation", normals=normal, loose=0.2)
    assert_allclose(prior.blocks[0], np.diag([0.2, 0.2, 1]))
    rot = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    q = make_prior(lead @ rot.T, ("a",), policy="orientation", normals=normal @ rot.T, loose=0.2)
    a = fit_prior(lead, prior, noise(3), alpha=0.1, source_ids=("a",))
    b = fit_prior(lead @ rot.T, q, noise(3), alpha=0.1, source_ids=("a",))
    assert_allclose(b.kernel, rot @ a.kernel, atol=1e-12)


@pytest.mark.parametrize("normal", [None, [[0, 0, 2]], [[np.nan, 0, 1]]])
def test_invalid_orientation_normal(normal):
    with pytest.raises(ValueError):
        make_prior(np.eye(3), ("a",), policy="orientation", normals=normal)


def test_patch_area_independent_right_triangle():
    vertices = np.array([[0, 0, 0], [0.003, 0, 0], [0, 0.004, 0]])
    areas = vertex_areas(vertices, [[0, 1, 2]])
    assert_allclose(areas, [2e-6] * 3, rtol=1e-14)
    assert_allclose(sum(areas), 0.5 * 0.003 * 0.004)
    with pytest.raises(ValueError):
        vertex_areas(vertices, [[0, 1, 2]], units="mm")


@pytest.mark.parametrize(
    "area,units",
    [([1, 2], "mm2"), ([0, 1], "m2"), ([-1, 1], "m2"), ([np.nan, 1], "m2"), ([1], "m2")],
)
def test_area_policy_rejects_wrong_units_and_shape(area, units):
    with pytest.raises(ValueError):
        make_prior(
            np.eye(2),
            ("a", "b"),
            orientation="fixed",
            policy="area",
            areas_m2=area,
            area_units=units,
        )


def test_density_quadrature_total_variance_stays_constant():
    for n in [2, 4, 8]:
        lead = np.ones((1, n))
        p = make_prior(
            lead,
            tuple(map(str, range(n))),
            orientation="fixed",
            policy="area",
            areas_m2=np.full(n, 0.01 / n),
        )
        assert_allclose(p.trace, 10.0)
        assert_allclose(np.sum(p.right(lead) * lead), 10.0)


def test_sensor_normalization_scalar_convention():
    lead = np.array([[1.0, 0.0], [0.0, 2.0]])
    p = make_prior(lead, ("a", "b"), orientation="fixed")
    q = normalize_prior(p, lead, noise(2), target=1)
    assert_allclose(q.blocks[:, 0, 0], [0.2, 0.2])
    assert_allclose(np.sum(q.right(lead) * lead), 1.0)
    assert_allclose(p.blocks[:, 0, 0], [1, 1])


def test_normalization_does_not_imply_unbiased_recovery():
    lead = np.ones((1, 2))
    p = make_prior(lead, ("a", "b"), orientation="fixed")
    q = normalize_prior(p, lead, noise(1))
    estimate = fit_prior(lead, q, noise(1), alpha=1, source_ids=("a", "b")).apply([1])
    assert_allclose(estimate, [0.25, 0.25])


def test_depth_cap_and_combined_area():
    lead = np.array([[10.0, 1.0]])
    p = make_prior(
        lead, ("a", "b"), orientation="fixed", policy="depth", depth_exponent=1, depth_cap=10
    )
    assert_allclose(p.blocks[:, 0, 0], [1, 10])
    q = make_prior(
        lead,
        ("a", "b"),
        orientation="fixed",
        policy="depth_area",
        depth_exponent=1,
        depth_cap=10,
        areas_m2=[0.002, 0.001],
    )
    assert_allclose(q.blocks[:, 0, 0], [2, 10])


def test_unobservable_prior_cannot_normalize():
    prior = SourcePrior(np.array([[[1.0]], [[0.0]]]), ("a", "b"), "MRI", "test", {})
    with pytest.raises(ValueError):
        normalize_prior(prior, [[0, 1]], noise(1))


def test_block_multiplication_against_independent_kronecker():
    lead = np.arange(18.0).reshape(3, 6)
    p = make_prior(lead, ("a", "b"), policy="orientation", normals=[[0, 0, 1], [1, 0, 0]])
    dense = np.zeros((6, 6))
    dense[:3, :3] = np.diag([0.2, 0.2, 1])
    dense[3:, 3:] = np.diag([1, 0.2, 0.2])
    assert_allclose(p.right(lead), lead @ dense)


@pytest.mark.parametrize("lambda2", [0.01, 1 / 9, 1.0])
def test_public_mne_uniform_agreement(lambda2):
    from soma.validation.mne_equivalence import uniform_mne_agreement

    result = uniform_mne_agreement(lambda2)
    assert result["relative_kernel_error"] < 1e-9


def test_prior_fingerprint_tracks_policy_scale_and_order():
    lead = np.array([[2.0, 1.0]])
    a = make_prior(lead, ("a", "b"), orientation="fixed")
    b = make_prior(lead, ("b", "a"), orientation="fixed")
    c = make_prior(lead, ("a", "b"), orientation="fixed", policy="depth")
    assert a.receipt()["source_order_sha256"] != b.receipt()["source_order_sha256"]
    assert a.receipt()["blocks_sha256"] != c.receipt()["blocks_sha256"]
    assert a.receipt() == make_prior(lead, ("a", "b"), orientation="fixed").receipt()


def test_depth_exponent_zero_is_uniform_without_truth():
    lead = np.arange(18.0).reshape(3, 6)
    prior = make_prior(lead, ("a", "b"), policy="depth", depth_exponent=0)
    assert_allclose(prior.blocks, np.broadcast_to(np.eye(3), (2, 3, 3)))


def test_orientation_zero_tangent_rank_deficient_allowed():
    p = make_prior(np.eye(3), ("a",), policy="orientation", normals=[[0, 0, 1]], loose=0)
    assert_allclose(
        fit_prior(np.eye(3), p, noise(3), alpha=0.1, source_ids=("a",)).kernel,
        np.diag([0, 0, 1 / 1.1]),
    )


def test_channel_projector_rank_normalization():
    from soma.source.noise import average_projector

    p = average_projector(3)
    n = NoiseModel(p, ("a", "b", "c"), p)
    prior = make_prior(p, ("a",), policy="uniform")
    normalized = normalize_prior(prior, p, n)
    assert_allclose(normalized.blocks[0], np.eye(3) / 2, atol=1e-14)
    assert_allclose(
        fit_prior(p, normalized, n, alpha=0.5, source_ids=("a",)).kernel, p / 2, atol=1e-14
    )
