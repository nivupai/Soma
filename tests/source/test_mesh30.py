"""Adversarial geometry, grid, resolution and independent mesher checks."""

import importlib.util

import numpy as np
import pytest

from soma.experiments.mesh_grid import design, protocol
from soma.source.bem_discrepancy import field_metrics, homogeneous_series, sensors
from soma.source.fem_reference import full_subtraction, radial_mesh
from soma.source.grid_diagnostics import resolution_difference, validate_evidence
from soma.source.mesh_replication import (
    audit_volume,
    boundaries,
    candidate_grid,
    gmsh_mesh,
    nearest_distances,
)
from soma.source.noise import average_projector


def test_frozen_design_and_correct_method_identities():
    c = design()
    p = protocol().protocol.document()
    assert c["parent_commit"] == "88fcda2f2d4fd4f215294fac966fa180a6594df9"
    assert c["grid"]["counts"] == [33, 147, 341]
    assert p["requirements"]["stages"]["inverse"]["implementation"] == "source.uncertainty.kernels"
    assert p["scientific"]["source_conductivity"]["sigmas_S_m"] == [0.33, 1.0, 0.004, 0.33]
    assert c["acceptance"]["matched_four_layer"] == 0.1


@pytest.mark.parametrize("step,count", [(30, 33), (20, 147), (15, 341)])
def test_frozen_grid_counts_and_nonleakage(step, count):
    g = candidate_grid(step).xyz
    assert len(g) == count and len(np.unique(g, axis=0)) == count
    assert np.linalg.norm(g, axis=1).max() <= 0.065 + 1e-12
    with pytest.raises(ValueError, match="leaked"):
        nearest_distances(g, g[:1])


def test_nearest_grid_distance_is_geometric_mm():
    grid = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    p = np.array([[0.01, 0.02, 0.0], [-0.01, 0, 0]])
    assert np.allclose(nearest_distances(grid, p), [np.sqrt(500), 10])
    assert np.allclose(nearest_distances(grid + 0.001, p + 0.001), [np.sqrt(500), 10])
    with pytest.raises(ValueError):
        nearest_distances(grid * 1000, p * 1000)


def test_independent_boundary_sampling_preserves_sensor_vertices():
    a = boundaries(0, 2)
    b = boundaries(0, 2, True)
    assert len(a[0].vertices.xyz) != len(b[0].vertices.xyz)
    assert all(np.linalg.norm(b[-1].vertices.xyz - p, axis=1).min() < 1e-14 for p in sensors(0))
    assert not np.array_equal(a[0].faces, b[0].faces)


@pytest.fixture(scope="module")
def mesh_fixture():
    bs = boundaries(None, 1)
    return (*radial_mesh(bs, 1)[:3], bs)


@pytest.mark.parametrize("fault", ["inverted", "label", "missing", "geometry"])
def test_volume_audit_rejects_incompatible_meshes(mesh_fixture, fault):
    v, t, labels, bs = mesh_fixture
    v = v.copy()
    t = t.copy()
    labels = labels.copy()
    if fault == "inverted":
        t[0, :2] = t[0, 1::-1]
    if fault == "label":
        labels[0] = 3
    if fault == "missing":
        t = t[1:]
        labels = labels[1:]
    if fault == "geometry":
        v[-1] *= 1.001
    with pytest.raises(ValueError):
        audit_volume(v, t, labels, bs)


@pytest.mark.parametrize("fault", ["grid_order", "units", "shape", "normalization"])
def test_resolution_comparisons_are_explicit(fault):
    g = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    a = np.eye(6)
    b = a.copy()
    other = g.copy()
    ua = ub = "1"
    if fault == "grid_order":
        other = other[::-1]
    if fault == "units":
        ub = "1/(A*m)"
    if fault == "shape":
        a = np.eye(3)
    if fault == "normalization":
        assert resolution_difference(2 * a, b, g, g, ua, ub) == 1
        return
    with pytest.raises(ValueError):
        resolution_difference(a, b, g, other, ua, ub)


@pytest.mark.parametrize("fault", ["mesher", "human_subjects", "threshold", "protocol"])
def test_unsupported_evidence_rejected(fault):
    value = dict(
        schema="soma.mesh-grid.explorer/1",
        synthetic_only=True,
        human_subjects=0,
        threshold=0.1,
        mesher="Gmsh4.15.2",
        protocol=protocol().protocol.fingerprint,
    )
    value[fault] = "fabricated" if fault in ["mesher", "protocol"] else 1
    with pytest.raises(ValueError):
        validate_evidence(value)


def test_scalar_alignment_cannot_hide_physical_error():
    a = np.arange(18, dtype=float).reshape(6, 3)
    a -= a.mean(axis=0)
    r = field_metrics(2 * a, a)
    assert r["relative"] == 1 and r["aligned_relative_diagnostic"] < 1e-12


@pytest.mark.skipif(importlib.util.find_spec("gmsh") is None, reason="external mesher extra")
def test_genuine_external_mesher_and_homogeneous_physics(monkeypatch):
    import soma.source.fem_reference as previous

    monkeypatch.setattr(
        previous, "radial_mesh", lambda *_: pytest.fail("external mesher called radial extrusion")
    )
    bs = boundaries(None, 1)
    v, t, labels, q = gmsh_mesh(bs, sensors(None), 0.025)
    assert q["mesher"] == "Gmsh" and q["boundary_coordinate_max_m"] == 0
    assert q["min_mean_ratio"] > 0.01 and q["native_minSICN"] > 0
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    g, d = full_subtraction(v, t, labels, p, sensors(None), [0.33] * 4, quadrature=8)
    exact = average_projector(32) @ homogeneous_series(p, sensors(None))
    assert (
        np.linalg.norm(g - exact) / np.linalg.norm(exact) < 0.15 and d["relative_residual"] < 1e-10
    )
    with pytest.raises(ValueError):
        full_subtraction(v, t, labels, p, sensors(None) * 1.001, [0.33] * 4)


def test_failure_accounting_cannot_drop_rejected_case():
    value = dict(
        schema="soma.mesh-grid.explorer/1",
        synthetic_only=True,
        human_subjects=0,
        threshold=0.1,
        mesher="Gmsh4.15.2",
        protocol=protocol().protocol.fingerprint,
        configurations=[dict(status="computed"), dict(status="FAILED")],
        receipt=dict(computed_fields=1, failed_fields=0),
    )
    with pytest.raises(ValueError, match="Unreported"):
        validate_evidence(value)


def test_reviewed_mesh_resource_rejects_corruption(tmp_path, monkeypatch):
    import json
    from importlib.resources import files

    from services.explorer_api import source_uncertainty as api

    value = json.loads(files("soma.resources").joinpath("mesh-grid-example-v30.json").read_text())
    validate_evidence(value)
    value["human_subjects"] = 1
    (tmp_path / "mesh-grid-example-v30.json").write_text(json.dumps(value))
    monkeypatch.setattr(api, "files", lambda _: tmp_path)
    with pytest.raises(ValueError, match="integrity"):
        api.mesh_grid_example()
