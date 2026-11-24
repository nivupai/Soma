"""Forward revalidation helpers: synthetic oracles and an MNE sample replay."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import ConvexHull

from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains, mesh_quality
from soma.imaging.surfaces import Mesh
from soma.source.cortical import subdivided_sphere
from soma.source.forward_revalidation import (
    average_reference,
    fixed_orientation,
    margin_strata,
    minimum_mesh_level,
    per_source,
    readiness_tag,
    relative_change,
    subdivide_midpoint,
    summarize,
)

PUBLIC = Path("experiments/milestone33/forward-revalidation.json")


def outward_sphere():
    v = subdivided_sphere("ico2") * 0.07
    f = np.asarray(ConvexHull(v).simplices, np.int64)
    tri = v[f]
    out = np.einsum("ij,ij->i", np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), tri[:, 0])
    f[out < 0] = f[out < 0][:, [0, 2, 1]]
    return v, f


def volume(v, f):
    t = v[f]
    return float(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6)


def test_subdivision_preserves_surface_and_winding():
    v, f = outward_sphere()
    v2, f2 = subdivide_midpoint(v, f)
    edges = len(f) * 3 // 2
    assert len(v2) == len(v) + edges and len(f2) == 4 * len(f)
    assert np.allclose(v2[: len(v)], v)
    assert volume(v2, f2) == pytest.approx(volume(v, f), rel=1e-12)
    q = mesh_quality(Mesh(Points(v2, Frame.MRI), f2))
    assert q["geometrically_valid_under_checks"] and q["outward_global_winding"]
    pts = np.random.default_rng(0).normal(size=(40, 3)) * 0.04
    a = contains(Mesh(Points(v, Frame.MRI), f), pts)
    b = contains(Mesh(Points(v2, Frame.MRI), f2), pts)
    assert np.array_equal(a, b)
    with pytest.raises(ValueError):
        subdivide_midpoint(v[:, :2], f)


def test_fixed_orientation_matches_dipole_projection_and_rotation():
    rng = np.random.default_rng(1)
    free = rng.normal(size=(5, 12))
    n = rng.normal(size=(4, 3))
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    expected = np.stack([free[:, 3 * i : 3 * i + 3] @ n[i] for i in range(4)], axis=1)
    assert np.allclose(fixed_orientation(free, n), expected)
    theta = 0.3
    r = np.array([[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
    # Coefficients in frame A, normals in frame B = r @ A: rotated field projects the same.
    n_a = n @ r  # r.T applied to each normal
    assert np.allclose(fixed_orientation(free, n, r), fixed_orientation(free, n_a))
    with pytest.raises(ValueError):
        fixed_orientation(free, n * 2)
    with pytest.raises(ValueError):
        fixed_orientation(free, n, 2 * r)
    with pytest.raises(ValueError):
        fixed_orientation(free[:, :11], n)


def test_relative_change_is_m32_metric_and_per_source_summaries():
    rng = np.random.default_rng(2)
    b = average_reference(rng.normal(size=(8, 6)))
    assert np.allclose(b.mean(axis=0), 0)
    a = 1.05 * b
    assert relative_change(a, b) == pytest.approx(0.05)
    ps = per_source(a, b)
    assert np.allclose(ps["relative_error"], 0.05)
    assert np.allclose(ps["correlation"], 1)
    assert np.allclose(ps["log_magnitude_ratio"], np.log(1.05))
    s = summarize(ps["relative_error"])
    assert s["p50"] == pytest.approx(0.05) and s["count"] == 6
    with pytest.raises(ValueError):
        relative_change(a, b[:, :5])
    with pytest.raises(ValueError):
        relative_change(a, 0 * b)
    with pytest.raises(ValueError):
        summarize(np.array([]))
    with pytest.raises(ValueError):
        average_reference(np.ones((1, 3)))


def test_margin_strata_restrict_sources():
    b = np.eye(3)[:, [0, 1, 2]] + 1.0
    a = b.copy()
    a[:, 0] *= 2  # only the near-skull source differs
    rows = margin_strata(a, b, np.array([0.0005, 0.003, 0.02]), (0.0, 1.0, 50.0))
    assert rows[0]["sources"] == 3 and rows[0]["relative"] > 0
    assert rows[1]["sources"] == 2 and rows[1]["relative"] == 0
    assert rows[2]["sources"] == 0 and rows[2]["relative"] is None
    with pytest.raises(ValueError):
        margin_strata(a, b, np.zeros(2), (0.0,))


def test_minimum_mesh_level_requires_passing_finest_chain():
    assert minimum_mesh_level([("3", "4", 0.08), ("4", "5", 0.03)]) == "3"
    assert minimum_mesh_level([("3", "4", 0.15), ("4", "5", 0.03)]) == "4"
    assert minimum_mesh_level([("3", "4", 0.05), ("4", "5", 0.12)]) is None
    assert minimum_mesh_level([("3", "4", float("nan"))]) is None
    with pytest.raises(ValueError):
        minimum_mesh_level([("3", "4", 0.05), ("5", "6", 0.01)])
    with pytest.raises(ValueError):
        minimum_mesh_level([])


def test_readiness_tag_never_claims_validation():
    tag = readiness_tag("QC_ONLY_ANATOMY", skull_ct_validated=False)
    assert tag["head_readiness"] == "QC_ONLY_ANATOMY"
    assert tag["anatomical_accuracy_established"] is False
    assert "not CT-validated" in tag["statement"]
    with pytest.raises(ValueError):
        readiness_tag("", skull_ct_validated=False)


def test_public_aggregate_is_tagged_and_path_free():
    if not PUBLIC.is_file():
        pytest.skip("Public forward revalidation aggregate not generated")
    text = PUBLIC.read_text()
    assert "/Users/" not in text and "reports/" not in text
    data = json.loads(text)
    assert data["head_readiness"] == "QC_ONLY_ANATOMY" and data["skull_ct_validated"] is False
    for row in data["refinement"] + data["solver_agreement"]:
        if "relative" in row:
            assert row["head_readiness"] == "QC_ONLY_ANATOMY"
            assert row["passed"] == (row["relative"] < row["target"])


@pytest.mark.integration
def test_mne_sample_forward_revalidation_replay():
    """Recompute public metrics from the private lead fields (never fetches data)."""
    work = Path(os.environ.get("SOMA_FORWARD_WORK", "reports/m33-forward"))
    if not (PUBLIC.is_file() and (work / "lead-4-mne.npy").is_file()):
        pytest.skip("Private forward revalidation lead fields required")
    data = json.loads(PUBLIC.read_text())
    for row in data["refinement"]:
        if "relative" not in row:
            continue
        a = np.load(work / f"lead-{row['coarse']}-mne.npy")
        b = np.load(work / f"lead-{row['fine']}-mne.npy")
        assert relative_change(a, b) == pytest.approx(row["relative"], rel=1e-12)
    for row in data["solver_agreement"]:
        if "relative" not in row:
            continue
        a = np.load(work / f"lead-{row['level']}-mne.npy")
        b = np.load(work / f"lead-{row['level']}-openmeeg.npy")
        assert relative_change(a, b) == pytest.approx(row["relative"], rel=1e-12)
        assert np.allclose(a.mean(axis=0), 0, atol=1e-12)
