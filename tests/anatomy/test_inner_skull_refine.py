import numpy as np

from soma.anatomy.inner_skull_refine import apply_correction, features, smooth_on_mesh, targets
from soma.imaging.volumes import Volume
from tests.anatomy.test_fs_skull import _icosphere


def _grid(shape=(60, 60, 60)):
    a = np.diag([0.001, 0.001, 0.001, 1.0])
    a[:3, 3] = -a[:3, :3] @ ((np.asarray(shape) - 1) / 2)
    return a


def test_constant_correction_moves_sphere_inward() -> None:
    sphere = _icosphere(0.02)
    moved = apply_correction(sphere, np.full(len(sphere.vertices.xyz), 2.0))
    r = np.linalg.norm(moved.vertices.xyz, axis=1).mean() * 1000
    assert abs(r - 18.0) < 0.05


def test_smoothing_preserves_constant_and_shrinks_spike() -> None:
    sphere = _icosphere(0.02)
    n = len(sphere.vertices.xyz)
    assert np.allclose(smooth_on_mesh(sphere, np.ones(n), 5), 1.0)
    spike = np.zeros(n)
    spike[0] = 10.0
    assert smooth_on_mesh(sphere, spike, 5)[0] < 5.0


def test_targets_are_signed_distance_and_features_are_mri_only() -> None:
    shape = (60, 60, 60)
    a = _grid(shape)
    idx = np.indices(shape) - (np.asarray(shape)[:, None, None, None] - 1) / 2
    r = np.sqrt((idx**2).sum(axis=0))
    cavity = Volume((r < 18).astype(np.uint8), a, "labels")
    sphere = _icosphere(0.02)  # 2 mm outside an 18 mm cavity
    y = targets(sphere, cavity)
    assert abs(float(np.median(y)) - 2.0) < 0.6
    t1 = Volume(np.where(r < 18, 100.0, 20.0).astype(np.float32), a)
    labels = np.zeros(shape, np.int16)
    labels[r < 18] = 24
    labels[r < 10] = 2
    x = features(sphere, t1, Volume(labels, a, "labels"))
    assert x.shape[0] == len(sphere.vertices.xyz) and np.isfinite(x).all()
