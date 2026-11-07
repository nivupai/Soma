import mne
import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.geometry import Electrodes, Frame, Points, SourceCoordinates, Transform


def test_rigid_roundtrip_and_mne():
    angle = 0.42
    c, s = np.cos(angle), np.sin(angle)
    matrix = np.eye(4)
    matrix[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    matrix[:3, 3] = [0.01, -0.02, 0.03]
    t = Transform(Frame.HEAD, Frame.TEMPLATE_MRI, matrix)
    p = Points(np.random.default_rng(1).normal(size=(20, 3)) * 0.05, Frame.HEAD)
    assert_allclose(t.inverse().apply(t.apply(p)).xyz, p.xyz, atol=1e-15)
    assert_allclose(t.then(t.inverse()).matrix, np.eye(4), atol=1e-15)
    assert_allclose(t.apply(p).xyz, mne.transforms.apply_trans(t.to_mne(), p.xyz))
    assert Transform.from_mne(t.to_mne(), template=True).destination == Frame.TEMPLATE_MRI
    assert Transform.from_mne(t.to_mne()).destination == Frame.MRI
    with pytest.raises(ValueError):
        t.apply(Points(p.xyz, Frame.MRI))
    with pytest.raises(ValueError):
        t.then(t)


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((3, 3)),
        np.diag([-1.0, 1, 1, 1]),
        np.diag([2.0, 1, 1, 1]),
        np.full((4, 4), np.nan),
        np.zeros((4, 4)),
    ],
)
def test_invalid_rigid(bad):
    with pytest.raises(ValueError):
        Transform(Frame.HEAD, Frame.MRI, bad)


def test_affine_requires_explicit_opt_in():
    t = Transform(Frame.MRI, Frame.TEMPLATE_MRI, np.diag([1.1, 1.2, 0.9, 1]), rigid=False)
    p = Points(np.array([[0.1, 0.02, -0.03]]), Frame.MRI)
    assert_allclose(t.inverse().apply(t.apply(p)).xyz, p.xyz)


@pytest.mark.parametrize(
    "xyz,unit",
    [
        (np.ones((2, 3)), "mm"),
        (np.ones((3, 2)), "m"),
        (np.ones((2, 3)) * 80, "m"),
        (np.full((2, 3), np.inf), "m"),
    ],
)
def test_invalid_points(xyz, unit):
    with pytest.raises(ValueError):
        Points(xyz, Frame.HEAD, unit)


def test_units_sources_and_scalp():
    p = Points.from_mm(np.array([[80.0, 0, 30], [-80, 0, 30]]), Frame.HEAD)
    sensors = Electrodes(("a", "b"), p)
    assert sensors.scalp_diagnostics(p)["max_distance_m"] == 0
    SourceCoordinates(p, (("lh", 3), ("rh", 3)))
    with pytest.raises(ValueError):
        SourceCoordinates(p, (("lh", 3), ("lh", 3)))
    with pytest.raises(ValueError):
        Electrodes(("a", "a"), p)
    with pytest.raises(ValueError):
        sensors.scalp_diagnostics(Points(p.xyz, Frame.MRI))
    with pytest.raises(ValueError):
        Electrodes(("a", "b"), Points(np.zeros((2, 3)), Frame.HEAD))
