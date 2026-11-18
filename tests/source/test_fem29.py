"""Independent PDE/source/geometry checks; no four-layer agreement manufactured."""

import importlib.util

import numpy as np
import pytest

from soma.anatomy.synthetic import sphere_mesh
from soma.experiments.fem_reference import design, protocol
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import homogeneous_series, sensors
from soma.source.fem_reference import (
    full_subtraction,
    layered_sphere_series,
    radial_mesh,
    tetra_quality,
)
from soma.source.noise import average_projector


@pytest.fixture(scope="module")
def volume():
    bs = []
    for radius in [0.081, 0.0828, 0.0873, 0.09]:
        v, f = sphere_mesh(1, radius)
        bs.append(Mesh(Points(v, Frame.MRI), f, {}))
    return radial_mesh(bs, 1)


def test_seal_and_prespecified_scope():
    c = design()
    p = protocol().protocol.document()
    assert p["optional_metadata"]["design"] == c
    assert c["sigmas_S_m"] == [0.33, 1.0, 0.004, 0.33]
    assert c["acceptance"]["independent_four_layer_relative"] == 0.1
    assert c["parent_pr"] == 13 and c["heads"] == list(range(6))


def test_exact_interface_conformity(volume):
    v, t, labels, q = volume
    assert q["exact_surface_facets"] and q["min_mean_ratio"] > 0.01
    assert all(n > 0 for n in q["tissue_counts"])
    assert q == dict(q) and len(labels) == len(t) and len(v) == 295


@pytest.mark.parametrize("bad", ["winding", "degenerate", "label", "millimetres"])
def test_mesh_rejections(volume, bad):
    v, t, labels, _ = volume
    v = v.copy()
    t = t.copy()
    labels = labels.copy()
    if bad == "winding":
        t[0, :2] = t[0, 1::-1]
    if bad == "degenerate":
        t[0, 1] = t[0, 0]
    if bad == "label":
        labels[0] = 9
    if bad == "millimetres":
        v *= 1000
    with pytest.raises(ValueError):
        tetra_quality(v, t, labels)


def test_concentric_homogeneous_identity_and_units():
    p = np.array([[0, 0, 0], [0.035, 0, 0], [0.02, 0.01, 0.045]])
    g, d = layered_sphere_series(p, sensors(None), [0.081, 0.0828, 0.0873, 0.09], [0.33] * 4)
    expected = average_projector(32) @ homogeneous_series(p, sensors(None))
    assert np.allclose(g, expected, rtol=1e-12, atol=1e-11)
    assert d["max_transmission_residual"] < 1e-12
    doubled, _ = layered_sphere_series(p, sensors(None), [0.081, 0.0828, 0.0873, 0.09], [0.66] * 4)
    assert np.allclose(2 * doubled, g, rtol=1e-12, atol=1e-11)
    assert np.max(np.abs(g.mean(axis=0))) < 1e-12


@pytest.mark.parametrize(
    "radii,sigmas",
    [
        ([0.081, 0.08, 0.0873, 0.09], [0.33] * 4),
        ([81, 82.8, 87.3, 90], [0.33] * 4),
        ([0.081, 0.0828, 0.0873, 0.09], [330] * 4),
    ],
)
def test_analytical_incompatible_contracts(radii, sigmas):
    with pytest.raises(ValueError):
        layered_sphere_series(np.zeros((1, 3)), sensors(None), radii, sigmas)


@pytest.mark.skipif(
    importlib.util.find_spec("skfem") is None, reason="optional independent FEM extra"
)
def test_small_independent_fem_physics(volume):
    v, t, labels, _ = volume
    p = np.array([[0, 0, 0], [0.02, 0, 0]])
    g, d = full_subtraction(v, t, labels, p, sensors(None), [0.33] * 4, quadrature=8)
    exact = average_projector(32) @ homogeneous_series(p, sensors(None))
    assert np.linalg.norm(g - exact) / np.linalg.norm(exact) < 0.15
    assert d["relative_residual"] < 1e-10 and d["preprojection_current_imbalance"] < 1e-5
    h, _ = full_subtraction(v, t, labels, p, sensors(None), [0.66] * 4, quadrature=8)
    assert np.allclose(g, 2 * h, rtol=1e-10, atol=1e-10)
    # Signed arbitrary moment and XYZ permutation are explicit linear contracts.
    m = np.array([2.0, -3.0, 1.0]) * 1e-8
    assert np.allclose(g[:, :3] @ (-m), -(g[:, :3] @ m), rtol=1e-14)
    assert not np.allclose(g[:, :3] @ m, g[:, [1, 0, 2]] @ m, atol=1e-12)
    assert np.max(np.abs(g.mean(axis=0))) < 1e-12


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(conductivity_unit="mS/m"),
        dict(frame="HEAD_mm"),
        dict(boundary="grounded"),
        dict(max_residual=1e-4),
        dict(quadrature=2),
    ],
)
def test_physical_contract_rejections(volume, kwargs):
    v, t, labels, _ = volume
    with pytest.raises(ValueError):
        full_subtraction(v, t, labels, np.zeros((1, 3)), sensors(None), [0.33] * 4, **kwargs)


@pytest.mark.skipif(
    importlib.util.find_spec("skfem") is None, reason="optional independent FEM extra"
)
@pytest.mark.parametrize("bad", ["source", "sensors", "nonconvergence"])
def test_source_reference_and_solver_guards(volume, bad):
    v, t, labels, _ = volume
    p = np.zeros((1, 3))
    ss = sensors(None)
    kw = {}
    if bad == "source":
        p[0] = [0.085, 0, 0]
    if bad == "sensors":
        ss = ss * 1.0001
    if bad == "nonconvergence":
        kw["max_residual"] = 1e-30
    with pytest.raises(ValueError):
        full_subtraction(v, t, labels, p, ss, [0.33] * 4, quadrature=8, **kw)


def test_unsupported_physical_claim_is_rejected(tmp_path):
    from soma.experiments.fem_reference import read_reference
    from soma.results.contracts import create_result
    from soma.results.io import save_result

    value = dict(
        schema="soma.fem-reference.receipt/1",
        protocol_fingerprint=protocol().protocol.fingerprint,
        synthetic_only=True,
        human_subjects=0,
        threshold=0.1,
        finest_head_relative=[0.2] * 6,
        independent_four_layer_agreement_pass=True,
        phantom="NOT_AVAILABLE",
        human_validation="NOT_ESTABLISHED",
    )
    domain = dict(
        computation="synthetic adversarial test",
        inputs={},
        environment={},
        assumptions=["synthetic"],
        validation={"scope": "test"},
        limitations=["not physical evidence"],
    )
    envelope = create_result(
        "experiment.manifest",
        domain,
        values=value,
        provenance={},
        method={"id": "test", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    target = tmp_path / "reports" / "reference"
    save_result(envelope, {}, target)
    with pytest.raises(ValueError, match="Unsupported"):
        read_reference(target / "result.json")


def test_synthetic_api_and_native_result():
    from services.explorer_api.source_uncertainty import fem_example

    r = fem_example()
    assert r["synthetic_only"] and r["human_subjects"] == 0 and r["threshold"] == 0.1
    assert len(r["heads"]) == 18 and r["receipt"]["models_failed"] == 1


def test_hierarchical_complete_independent_units_required():
    from soma.experiments.nonspherical import hierarchical

    with pytest.raises(ValueError):
        hierarchical(np.zeros((72, 3)))
    with pytest.raises(ValueError):
        hierarchical(np.full((6, 12), np.nan))


def test_radial_mesh_rejects_winding_and_nonmatching_interfaces():
    bs = []
    for radius in [0.081, 0.0828, 0.0873, 0.09]:
        v, f = sphere_mesh(1, radius)
        bs.append(Mesh(Points(v, Frame.MRI), f, {}))
    bs = [Mesh(b.vertices, b.faces[:, [1, 0, 2]], {}) for b in bs]
    with pytest.raises(ValueError, match="Outward"):
        radial_mesh(bs, 1)


def test_shipped_fem_resource_corruption_is_rejected(tmp_path, monkeypatch):
    import json
    from importlib.resources import files

    from services.explorer_api import source_uncertainty as api

    value = json.loads(
        files("soma.resources").joinpath("fem-reference-example-v29.json").read_text()
    )
    value["human_subjects"] = 1
    (tmp_path / "fem-reference-example-v29.json").write_text(json.dumps(value))
    monkeypatch.setattr(api, "files", lambda _: tmp_path)
    with pytest.raises(ValueError, match="integrity"):
        api.fem_example()
