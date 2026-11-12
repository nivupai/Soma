"""Adversarial physical contracts and independent small reference computations."""

import importlib.util

import numpy as np
import pandas as pd
import pytest

from soma.experiments.nonspherical import aggregate, hierarchical, known_truth
from soma.geometry import Frame, Points, Transform
from soma.imaging.surfaces import Mesh
from soma.protocol.model import SealedProtocol
from soma.results.contracts import canonical
from soma.source.nonspherical import (
    check_protocol,
    check_sources,
    convergence,
    design,
    head_parameters,
    meshes,
    native_forward,
    pose,
    protocol,
    radial_projection,
    sensor_targets,
    source_grid,
    validate_meshes,
)
from soma.source.nonspherical_solver import solve


def test_frozen_identity_and_amendment():
    p = protocol()
    check_protocol(p)
    assert p.protocol.document()["amendment"]["outcome_inspection"] == "no"
    assert design()["candidate_radii_mm"] == [35, 55]
    assert design()["reference_hierarchy"]["C"].endswith("NOT_ESTABLISHED")


def test_corrupt_receipt():
    d = protocol().record()
    d["seal_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        SealedProtocol(canonical(d)).record()


@pytest.mark.parametrize("head", range(6))
def test_head_geometry_and_truth(head):
    p = head_parameters(head)
    b = meshes(p, 0)
    q = validate_meshes(b)
    assert q["minimum_thickness_mm"] > 0.4
    check_sources(b[0], source_grid())
    truth, m = known_truth(head)
    check_sources(meshes(p, 1)[0], truth)
    assert np.allclose(np.linalg.norm(m, axis=1), 1e-8, rtol=1e-12, atol=0)
    assert not np.allclose(p["axes"], [1, 1, 1])
    assert np.array_equal(known_truth(head)[0].xyz, truth.xyz)


@pytest.mark.parametrize("bad", [-1, 6, 42])
def test_unplanned_head(bad):
    with pytest.raises(ValueError):
        head_parameters(bad)


@pytest.mark.parametrize(
    "kind", ["inverted", "non_nested", "self_intersecting", "open", "wrong_frame", "collapsed"]
)
def test_reject_invalid_mesh(kind):
    b = meshes(head_parameters(0), 0)
    v = b[0].vertices.xyz.copy()
    f = b[0].faces.copy()
    frame = Frame.MRI
    if kind == "inverted":
        f = f[:, [0, 2, 1]]
    if kind == "non_nested":
        v *= 2
    if kind == "self_intersecting":
        v[0] *= -2
    if kind == "open":
        f = f[:-1]
    if kind == "wrong_frame":
        frame = Frame.HEAD
    if kind == "collapsed":
        v[0] = v[1]
    b[0] = Mesh(Points(v, frame), f)
    with pytest.raises(ValueError):
        validate_meshes(b)


@pytest.mark.parametrize("kind", ["outside", "frame", "margin"])
def test_dipole_contract(kind):
    b = meshes(head_parameters(0), 0)
    p = (
        Points([[1.0, 0, 0]], Frame.MRI)
        if kind == "outside"
        else Points([[0.0, 0, 0]], Frame.HEAD)
        if kind == "frame"
        else Points([b[0].vertices.xyz[0] * 0.999], Frame.MRI)
    )
    with pytest.raises(ValueError):
        check_sources(b[0], p)


def test_convergence_not_manufactured():
    assert convergence([0.4, 0.12, 0.03])["status"] == "CONVERGED"
    assert convergence([0.4, 0.12, 0.06])["status"] == "NOT_CONVERGED"
    assert convergence([0.01, 0.02, 0.01])["status"] == "NOT_CONVERGED"
    with pytest.raises(ValueError):
        convergence([0.1, np.nan, 0.01])
    with pytest.raises(ValueError):
        convergence([0.1, 0.01])


@pytest.mark.parametrize("kind", ["matrix", "transform", "nonfinite"])
def test_native_contract(kind):
    grid = Points(source_grid().xyz[:2], Frame.MRI)
    ss, _ = radial_projection(meshes(head_parameters(0), 0)[-1], sensor_targets(head_parameters(0)))
    g = np.ones((32, 6))
    if kind == "matrix":
        g = g[:, :3]
    if kind == "nonfinite":
        g[0, 0] = np.nan
    t = Transform(Frame.MRI, Frame.HEAD, np.eye(4)) if kind == "transform" else pose({})
    with pytest.raises(ValueError):
        native_forward(g, grid, ss, t)


def test_hierarchical_noise_is_not_independent():
    a = np.arange(72).reshape(6, 12)
    assert hierarchical(a) == hierarchical(a)
    assert hierarchical(a)[0] == a.mean()
    assert hierarchical(np.ones((6, 12))) == (1, 1, 1)
    with pytest.raises(ValueError):
        hierarchical(np.ones((72, 8)))


def test_duplicate_and_unknown_pairings():
    row = dict(
        head=0,
        case="mesh-2",
        source=0,
        noise_std_V=0.0,
        draw=0,
        method="MNE",
        status="computed",
        localization_mm=1.0,
        dispersion_mm=2.0,
        peak_amplitude_bias_ratio=0.0,
    )
    with pytest.raises(ValueError):
        aggregate(pd.DataFrame([row, row]))
    with pytest.raises(ValueError):
        aggregate(pd.DataFrame([dict(row, source=12)]))
    with pytest.raises(ValueError):
        aggregate(pd.DataFrame([dict(row, draw=1)]))
    out = aggregate(pd.DataFrame([row]))
    assert (out.status == "INCOMPLETE").all()
    assert out.localization_mm.isna().all()


@pytest.mark.parametrize("kind", ["conductivity", "sensor", "dipole", "topology"])
def test_solver_input_rejection(tmp_path, kind):
    b = meshes(head_parameters(0), 0)
    ss, _ = radial_projection(b[-1], sensor_targets(head_parameters(0)))
    sigmas = design()["conductivities_S_m"]
    pts = np.zeros((1, 3))
    if kind == "conductivity":
        sigmas = [330, 1000, 4, 330]
    if kind == "sensor":
        ss *= 0.5
    if kind == "dipole":
        pts[:] = 1
    if kind == "topology":
        b = b[:2]
    with pytest.raises(ValueError):
        solve(b, pts, ss, sigmas, tmp_path / "bad")


def test_worker_divergence_is_retained(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import soma.source.nonspherical_solver as module

    b = meshes(head_parameters(0), 0)
    ss, _ = radial_projection(b[-1], sensor_targets(head_parameters(0)))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=2, stdout="ArithmeticError: solver divergence\n"
        ),
    )
    with pytest.raises(ValueError, match="divergence"):
        solve(b, np.zeros((1, 3)), ss, design()["conductivities_S_m"], tmp_path / "bad")
    assert "divergence" in (tmp_path / "bad/solver.log").read_text()


@pytest.mark.skipif(
    importlib.util.find_spec("openmeeg") is None, reason="optional conductor solver"
)
def test_exact_homogeneous_reference(tmp_path):
    from soma.anatomy.synthetic import sphere_mesh
    from soma.source.noise import average_projector

    u, _ = sphere_mesh(0, 1)
    sensors = u * 0.09
    exact = average_projector(len(u)) @ (3 / (4 * np.pi * 0.33 * 0.09**3) * sensors)
    errors = []
    for level in (1, 2):
        v, f = sphere_mesh(level, 0.09)
        g, d = solve(
            [Mesh(Points(v, Frame.MRI), f)],
            np.zeros((1, 3)),
            sensors,
            [0.33],
            tmp_path / str(level),
        )
        errors.append(np.linalg.norm(g - exact) / np.linalg.norm(exact))
        assert d["algebraic_residual_relative"] < 1e-8
        assert d["reference_null_relative"] < 1e-12
    assert errors[1] < 0.04
    assert errors[1] < errors[0] * 0.4


def test_wrong_conductivity_unit(tmp_path):
    b = meshes(head_parameters(0), 0)
    ss, _ = radial_projection(b[-1], sensor_targets(head_parameters(0)))
    with pytest.raises(ValueError, match="unit"):
        solve(
            b,
            np.zeros((1, 3)),
            ss,
            design()["conductivities_S_m"],
            tmp_path / "bad",
            conductivity_unit="mS/m",
        )


def test_invalid_orientation_and_sensor_target():
    from soma.source.nonspherical import boundary_points

    with pytest.raises(ValueError, match="Unit directions"):
        boundary_points(head_parameters(0), 0, np.array([[1.0, 1.0, 1.0]]))
    with pytest.raises(ValueError, match="sensor targets"):
        radial_projection(meshes(head_parameters(0), 0)[-1], np.zeros((1, 3)))


def test_synthetic_export_and_receipt(tmp_path):
    from soma.eeg_benchmark.evaluation import environment_snapshot
    from soma.experiments.nonspherical import read_nonspherical
    from soma.results.contracts import create_result
    from soma.results.io import save_result

    domain = dict(
        computation="synthetic",
        inputs={},
        environment=environment_snapshot(),
        assumptions=[],
        validation={},
        limitations=["test"],
    )
    values = dict(synthetic_only=False, human_subjects=1, design_sha256="wrong")
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=values,
        provenance={},
        method={"id": "soma.nonspherical", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    save_result(envelope, {}, tmp_path / "result")
    with pytest.raises(ValueError, match="synthetic"):
        read_nonspherical(tmp_path / "result/result.json")


def test_explorer_only_reviewed_synthetic_artifact():
    from services.explorer_api.source_uncertainty import nonspherical_example

    value = nonspherical_example()
    assert len(value["heads"]) == 6
    assert value["human_subjects"] == 0 and value["synthetic_only"]
    assert len(value["convergence"]) == 6
    assert all(len(h["display_meshes"]["2"]) == 4 for h in value["heads"])


@pytest.mark.skipif(
    importlib.util.find_spec("openmeeg") is None, reason="optional conductor solver"
)
def test_four_layer_native_inverse_and_orientation(tmp_path):
    from soma.source.uncertainty import kernels

    b = meshes(head_parameters(0), 0)
    ss, _ = radial_projection(b[-1], sensor_targets(head_parameters(0)))
    points = Points(source_grid().xyz[:2], Frame.MRI)
    g, d = solve(b, points.xyz, ss, design()["conductivities_S_m"], tmp_path / "four")
    assert d["layers"] == 4 and d["algebraic_residual_relative"] < 1e-8
    t = pose(dict(rotation_deg=1.0, translation_mm=1.0))
    fw = native_forward(g, points, t.inverse().apply(Points(ss, Frame.MRI)).xyz, t)
    expected = (g.reshape(32, 2, 3) @ t.matrix[:3, :3]).reshape(32, 6)
    assert np.allclose(fw.matrix, expected, atol=1e-10, rtol=1e-12)
    ops, check = kernels(fw, float(np.linalg.norm(g, 2)))
    assert set(ops) == {"Tikhonov", "MNE", "dSPM"}
    assert check["svd_vs_independent_solve_relative"] < 1e-10


def test_native_synthetic_result_roundtrip(tmp_path):
    from soma.eeg_benchmark.evaluation import environment_snapshot
    from soma.experiments.nonspherical import read_nonspherical
    from soma.results.contracts import create_result
    from soma.results.io import save_result
    from soma.source.nonspherical import DESIGN_SHA

    values = dict(
        synthetic_only=True,
        human_subjects=0,
        design_sha256=DESIGN_SHA,
        protocol_fingerprint=protocol().protocol.fingerprint,
    )
    domain = dict(
        computation="synthetic",
        inputs={},
        environment=environment_snapshot(),
        assumptions=[],
        validation={},
        limitations=["test"],
    )
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=values,
        provenance={},
        method={"id": "soma.nonspherical", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    path = save_result(envelope, {}, tmp_path / "result")
    assert read_nonspherical(path) == values
