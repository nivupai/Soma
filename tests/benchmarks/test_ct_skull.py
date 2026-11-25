"""CT skull truth, region rule, exclusion flags and metrics on a concentric-shell phantom."""

import numpy as np
import pytest

from soma.anatomy.t1_skull import T1SkullParameters, estimate_t1_skull
from soma.benchmarks.ct_skull import (
    CTSkullParameters,
    FlagThresholds,
    RegionRule,
    boundary_metrics,
    ct_truth,
    exclusion_flags,
    score_case,
    superior_axis,
)
from soma.imaging.volumes import Volume
from tests.skull_phantom import INNER, OUTER, SCALP, phantom, radius_mm

SMALL_HEAD = FlagThresholds(minimum_cavity_ml=300.0)


def _radius(mesh) -> float:
    return float(np.linalg.norm(mesh.vertices.xyz, axis=1).mean() * 1000)


@pytest.fixture(scope="module")
def case():
    ph = phantom()
    truth = ct_truth(ph["ct"], ph["mask"])
    region = RegionRule().fit(truth.masks["inner_skull"])
    return ph, truth, region


def _with_ct(ph, ct: np.ndarray) -> Volume:
    return Volume(ct.astype(np.float32), ph["ct"].affine_m, "intensity", ph["ct"].metadata)


def test_superior_axis_of_lps_grid() -> None:
    assert superior_axis(phantom()["ct"]) == (2, 1)


def test_truth_recovers_shell_radii(case) -> None:
    _, truth, _ = case
    for name, expected in (("inner_skull", INNER), ("outer_skull", OUTER), ("outer_scalp", SCALP)):
        assert abs(_radius(truth.meshes[name]) - expected) < 1.0, name
    assert truth.provenance["parameters"]["bone_hu"] == 300.0


@pytest.mark.parametrize("hu", [200.0, 400.0])
def test_sensitivity_thresholds_are_parameters(hu: float) -> None:
    ph = phantom()
    truth = ct_truth(ph["ct"], ph["mask"], parameters=CTSkullParameters(bone_hu=hu))
    assert truth.provenance["parameters"]["bone_hu"] == hu
    assert abs(_radius(truth.meshes["inner_skull"]) - INNER) < 1.0


def test_region_excludes_inferior_band_and_orbit_box(case) -> None:
    _, _, region = case
    z_lo, z_hi, _, y_hi = region.extent_mm
    assert np.isclose(region.plane_z_mm, z_lo + 0.4 * (z_hi - z_lo))
    probes = np.array(
        [
            [0.0, 0.0, z_hi - 1],  # vertex: kept
            [0.0, 0.0, z_lo + 1],  # inferior: excluded
            [0.0, y_hi - 1, region.plane_z_mm + 1],  # anterior-low: orbit box, excluded
            [0.0, -y_hi + 1, region.plane_z_mm + 1],  # posterior same height: kept
        ]
    )
    assert region.contains_mm(probes).tolist() == [True, False, False, True]
    assert region.provenance()["fitted_on"] == "CT cranial cavity only"


def test_identical_surfaces_score_zero(case) -> None:
    _, truth, region = case
    mesh = truth.meshes["outer_skull"]
    m = boundary_metrics(mesh, mesh, region, truth_mask=truth.masks["outer_skull"])
    assert m["mean_abs_mm"] < 1e-9 and m["HD95_mm"] < 1e-9


def test_baseline_offset_error_has_expected_sign_and_size(case) -> None:
    ph, truth, region = case
    est = estimate_t1_skull(
        ph["t1"],
        ph["synthseg"],
        parameters=T1SkullParameters(outer_offset_mm=4.0),
        check_nesting=False,
    )
    scores = score_case(est.meshes, est.masks, truth, region)
    outer = scores["boundaries"]["outer_skull"]
    assert -3.0 < outer["signed_mean_mm"] < -1.0  # 4 mm prior vs 6 mm CT bone: inside
    assert abs(scores["boundaries"]["inner_skull"]["signed_mean_mm"]) < 0.5
    assert -3.0 < scores["thickness"]["mean_error_mm"] < -1.0
    assert 5.0 < scores["thickness"]["ct_mean_thickness_mm"] < 7.0


def test_contains_and_trilinear_signs_agree() -> None:
    ph = phantom(voxel_mm=4.0, shape=(40, 40, 40))
    truth = ct_truth(
        ph["ct"],
        ph["mask"],
        parameters=CTSkullParameters(enclosure_closing_voxels=2, padding_voxels=4),
    )
    region = RegionRule().fit(truth.masks["inner_skull"])
    est = estimate_t1_skull(
        ph["t1"],
        ph["synthseg"],
        parameters=T1SkullParameters(
            outer_offset_mm=3.0, inner_closing_voxels=1, scalp_closing_voxels=1, padding_voxels=2
        ),
        check_nesting=False,
    )
    estimate, reference = est.meshes["outer_skull"], truth.meshes["outer_skull"]
    mask = truth.masks["outer_skull"]
    fast = boundary_metrics(estimate, reference, region, truth_mask=mask, contains_budget=0)
    assert fast["sign_method"].startswith("trilinear")
    assert fast["contains_audit"]["agreement"] == 1.0
    exact = boundary_metrics(estimate, reference, region, truth_mask=mask, contains_budget=1e12)
    assert exact["sign_method"].startswith("contains")
    assert exact["signed_mean_mm"] < -1.0
    assert np.isclose(exact["signed_mean_mm"], fast["signed_mean_mm"], atol=1e-6)


def test_clean_phantom_raises_no_flags(case) -> None:
    ph, truth, region = case
    flags = exclusion_flags(ph["ct"], ph["mask"], truth, region, t1=ph["t1"], thresholds=SMALL_HEAD)
    assert not flags["any"]
    assert flags["mr_ct_consistency"]["ct_bone_dark_in_mr_fraction"] > 0.9


def test_metal_flag(case) -> None:
    ph, truth, region = case
    ct = ph["ct"].array().copy()
    centre = np.array(ct.shape) // 2
    ct[centre[0] - 2 : centre[0] + 2, centre[1] - 2 : centre[1] + 2, -14:-11] = 3500.0
    flags = exclusion_flags(_with_ct(ph, ct), ph["mask"], truth, region, thresholds=SMALL_HEAD)
    assert flags["metal"]["flag"] and flags["metal"]["voxels_in_region"] > 10
    assert flags["mr_ct_consistency"]["flag"] is None  # reported as unsupported, not passed


def test_vertex_truncation_flag_uses_superior_end(case) -> None:
    ph, truth, region = case
    for edge, expected in ((slice(-2, None), True), (slice(0, 2), False)):
        # Tissue at the superior (+k on LPS) edge is truncation; at the neck end it is not.
        ct, head = ph["ct"].array().copy(), ph["mask"].array().copy()
        ct[30:50, 30:50, edge] = 40.0
        head[30:50, 30:50, edge] = 1
        mask = Volume(head, ph["mask"].affine_m, "labels", ph["mask"].metadata)
        flags = exclusion_flags(_with_ct(ph, ct), mask, truth, region, thresholds=SMALL_HEAD)
        assert flags["vertex_truncation"]["flag"] is expected


def test_skull_defect_flag() -> None:
    ph = phantom()
    ct = ph["ct"].array().copy()
    r = radius_mm(ct.shape, 2.0)
    k = np.indices(ct.shape)[2]
    hole = (r >= INNER - 1) & (r < OUTER) & (k > 39 + 22)  # vertex cap, ~35 mm wide
    ct[hole] = 30.0
    defect = _with_ct(ph, ct)
    truth = ct_truth(
        defect,
        ph["mask"],
        parameters=CTSkullParameters(enclosure_closing_voxels=9, padding_voxels=10),
    )
    region = RegionRule().fit(truth.masks["inner_skull"])
    flags = exclusion_flags(defect, ph["mask"], truth, region, thresholds=SMALL_HEAD)
    assert flags["skull_defect"]["flag"]
    assert flags["skull_defect"]["largest_uncovered_patch_mm2"] >= 200.0


def test_mr_ct_consistency_flag(case) -> None:
    ph, truth, region = case
    t1 = ph["t1"].array().copy()
    t1[t1 == np.float32(0.05)] = 0.8  # MR shows no dark bone where CT has bone
    bright = Volume(t1, ph["t1"].affine_m, "intensity", ph["t1"].metadata)
    flags = exclusion_flags(ph["ct"], ph["mask"], truth, region, t1=bright, thresholds=SMALL_HEAD)
    assert flags["mr_ct_consistency"]["flag"]


def test_cavity_not_split_by_axial_slice_with_open_bone_ring() -> None:
    # v1 regression: an axial slice whose bone ring is open (sinus, orbit roof) must not cut
    # the cranial cavity into slabs.
    base = phantom()
    ct = base["ct"].array().copy()
    r = radius_mm(ct.shape, 2.0)
    k = ct.shape[2] // 2 + 5
    shell = (r >= INNER) & (r < OUTER)
    gap = np.zeros_like(shell)
    gap[: ct.shape[0] // 2 - 8, :, k : k + 12] = True  # open the ring on one side, 24 mm tall
    ct[shell & gap] = 40.0
    truth = ct_truth(
        Volume(ct, base["ct"].affine_m, "intensity", base["ct"].metadata), base["mask"]
    )
    full = ct_truth(base["ct"], base["mask"])
    cavity = truth.masks["inner_skull"].array().sum()
    assert cavity > 0.8 * full.masks["inner_skull"].array().sum()
