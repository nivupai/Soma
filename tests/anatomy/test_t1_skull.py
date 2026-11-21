"""T1-only baseline on a concentric-shell phantom: radii, offset prior, clipping, MNE export."""

import numpy as np
import pytest

from soma.anatomy.t1_skull import (
    METHOD,
    MNE_SURFACE_IDS,
    T1SkullParameters,
    estimate_t1_skull,
    pad,
)
from tests.skull_phantom import INNER, OUTER, SCALP, phantom


def _radius(mesh) -> float:
    return float(np.linalg.norm(mesh.vertices.xyz, axis=1).mean() * 1000)


@pytest.fixture(scope="module")
def estimate():
    ph = phantom()
    return estimate_t1_skull(ph["t1"], ph["synthseg"], check_nesting=False)


def test_boundaries_recover_phantom_radii(estimate) -> None:
    for name, expected in (("inner_skull", INNER), ("outer_skull", OUTER), ("outer_scalp", SCALP)):
        assert abs(_radius(estimate.meshes[name]) - expected) < 1.0, name


def test_provenance_labels_baseline_and_records_parameters(estimate) -> None:
    prov = estimate.provenance
    assert prov["method"] == METHOD
    assert "offset prior, not measured" in prov["method"]
    assert prov["readiness"] == "NOT_READY"
    assert prov["outer_skull_measured"] is False
    assert prov["parameters"]["outer_offset_mm"] == 6.0
    assert prov["parameters"]["scalp_margin_mm"] == 2.0
    assert prov["scalp_threshold_rule"] == "Otsu"


def test_mne_records_plug_into_conductor_path(estimate) -> None:
    records = estimate.mne_surfaces()
    assert [r["id"] for r in records] == [1, 3, 4]
    assert MNE_SURFACE_IDS == {"inner_skull": 1, "outer_skull": 3, "outer_scalp": 4}
    assert all(r["coord_frame"] == 5 for r in records)
    conductor = estimate.conductor("phantom")
    radii = [_radius(m) for m in conductor.meshes]
    assert radii == sorted(radii)  # from_mne orders inner skull, outer skull, scalp


def test_offset_is_an_explicit_parameter() -> None:
    ph = phantom()
    est = estimate_t1_skull(
        ph["t1"],
        ph["synthseg"],
        parameters=T1SkullParameters(outer_offset_mm=4.0),
        check_nesting=False,
    )
    assert abs(_radius(est.meshes["outer_skull"]) - (INNER + 4.0)) < 1.0
    assert est.provenance["parameters"]["outer_offset_mm"] == 4.0


def test_outer_skull_clipped_inside_scalp_margin() -> None:
    ph = phantom(outer=55.0, scalp=57.0)
    est = estimate_t1_skull(ph["t1"], ph["synthseg"], check_nesting=False)
    assert est.provenance["clipping"]["outer_voxels_removed_by_scalp_margin"] > 0
    outer = np.linalg.norm(est.meshes["outer_skull"].vertices.xyz, axis=1).max() * 1000
    assert outer <= 57.0 - 2.0 + 1.0  # margin, plus half a 2 mm voxel of marching cubes


def test_coarse_phantom_is_geometrically_nested() -> None:
    ph = phantom(voxel_mm=4.0, shape=(40, 40, 40))
    est = estimate_t1_skull(
        ph["t1"],
        ph["synthseg"],
        parameters=T1SkullParameters(
            inner_closing_voxels=1, scalp_closing_voxels=1, padding_voxels=2
        ),
    )
    assert est.nesting is not None and est.nesting["geometric_candidate"]
    assert est.provenance["geometric_candidate"] is True


def test_padding_keeps_physical_positions() -> None:
    vol = phantom(voxel_mm=4.0, shape=(40, 40, 40))["t1"]
    padded = pad(vol, 3)
    a = vol.grid.to_world(np.array([[0.0, 0.0, 0.0]])).xyz
    b = padded.grid.to_world(np.array([[3.0, 3.0, 3.0]])).xyz
    assert np.allclose(a, b)


def test_invalid_parameters_refused() -> None:
    with pytest.raises(ValueError):
        T1SkullParameters(outer_offset_mm=0)
    with pytest.raises(ValueError):
        T1SkullParameters(padding_voxels=2, scalp_closing_voxels=3)
