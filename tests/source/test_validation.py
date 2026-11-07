import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.experiments.source_simulation import source_waveforms
from soma.source.benchmark import numerical_benchmarks
from soma.source.inverse import Tikhonov
from soma.source.resolution import cortical_distances
from soma.source.sensitivity import sphere_sensitivity


def test_numerical_benchmark_identifiable_accuracy():
    rows = numerical_benchmarks()
    assert len(rows) == 24
    for row in rows:
        if row["lambda2"] == 0 and row["case"] in ("identity", "diagonal", "overdetermined"):
            assert row["relative_source_error"] < 1e-12
            assert row["forward_consistency_relative"] < 1e-12


@pytest.mark.parametrize(
    "matrix,lam",
    [(np.ones(3), 1), (np.eye(2), -1), (np.eye(2), np.nan), (np.full((2, 2), np.inf), 1)],
)
def test_invalid_inverse(matrix, lam):
    with pytest.raises(ValueError):
        Tikhonov(matrix, lam)


def test_mesh_geodesic_is_not_euclidean_or_interhemisphere():
    # Mesh edges force a path via (1,0); straight line to (1,1) is shorter.
    rr = np.array([[0.0, 0, 0], [1, 0, 0], [1, 1, 0], [2, 0, 0]]) * 0.01
    surface = {"rr": rr, "tris": np.array([[0, 1, 3], [1, 2, 3]]), "vertno": np.array([0, 2])}
    distances = cortical_distances([surface, surface], [0, 3])
    assert_allclose(distances[0, :2], [0, 0.02])
    assert distances[0, 1] > np.linalg.norm(rr[0] - rr[2])
    assert np.isinf(distances[0, 2:]).all()
    assert distances[1, 3] == 0


def test_neurodsp_current_waveforms():
    x, metadata = source_waveforms("bursts", 160, 4, 1e-8)
    t = np.arange(640) / 160
    assert np.max(np.abs(x[0])) == pytest.approx(1e-8, rel=1e-12)
    assert np.all(x[0, t < 0.5] == 0)
    assert metadata["burst_intervals_s"] == [[0.5, 1.25], [2.5, 3.25]]
    x, _ = source_waveforms("correlated", 160, 4, 1e-8)
    assert_allclose(x[1], x[0] * 0.8)


def test_actual_recomputed_sphere_conductivity():
    summary, arrays = sphere_sensitivity()
    assert 0.1 < summary["relative_matrix_perturbation"] < 1
    assert arrays["baseline"].shape == (13, 12)
    assert not np.allclose(arrays["baseline"], arrays["changed"])
    assert_allclose(arrays["baseline"].sum(axis=0), np.zeros(12), atol=1e-12)
