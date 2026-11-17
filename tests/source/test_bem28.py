"""Physical equivalence, independent analytical checks and adversarial contracts."""

import importlib.util

import numpy as np
import pytest

from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.protocol.model import Protocol, SealedProtocol, seal
from soma.results.contracts import canonical
from soma.source.bem_discrepancy import (
    DESIGN_SHA,
    contract_hashes,
    design,
    field_metrics,
    geometry,
    homogeneous_series,
    match,
    protocol,
    sensors,
    solve,
    triangle_signature,
    validate,
)


def test_frozen_identity():
    assert design()["thresholds"]["independent_agreement"] == 0.10
    assert design()["heldout_head"] == 5
    assert protocol().protocol.document()["optional_metadata"]["design_sha256"] == DESIGN_SHA


@pytest.mark.parametrize(
    "part", ["geometry", "sources", "sensors", "conductivity", "reference", "frame"]
)
def test_contract_mismatch(part):
    b = geometry(0, [1] * 3)
    a = contract_hashes(
        [(m.vertices.xyz, m.faces) for m in b], np.zeros((1, 3)), sensors(0), [0.33, 0.004, 0.33]
    )
    bad = dict(a)
    bad[part] = "0" * 64
    with pytest.raises(ValueError, match="Unmatched"):
        match(a, bad)


@pytest.mark.parametrize(
    "kind", ["winding", "nesting", "unit", "source", "sensor", "conductivity", "projection"]
)
def test_invalid_geometry(kind):
    b = geometry(0, [1] * 3)
    p = np.zeros((1, 3))
    ss = sensors(0)
    sigmas = [0.33, 0.004, 0.33]
    if kind == "winding":
        b[0] = Mesh(b[0].vertices, b[0].faces[:, [0, 2, 1]])
    if kind == "nesting":
        b[0] = Mesh(Points(b[0].vertices.xyz * 2, Frame.MRI), b[0].faces)
    if kind == "unit":
        with pytest.raises(ValueError, match="millimetres versus metres"):
            Points(b[0].vertices.xyz * 1000, Frame.MRI)
        return
    if kind == "source":
        p[:] = 0.2
    if kind == "sensor":
        ss = ss[:31]
    if kind == "projection":
        ss = ss * 1.01
    if kind == "conductivity":
        sigmas = [330.0, 4.0, 330.0]
    with pytest.raises(ValueError):
        validate(b, p, ss, sigmas)


def test_central_sphere_and_sigma_scaling():
    ss = sensors(None)
    p = np.zeros((1, 3))
    g = homogeneous_series(p, ss)
    exact = 3 * ss / (4 * np.pi * 0.33 * 0.09**3)
    np.testing.assert_allclose(g, exact, rtol=1e-13, atol=1e-12)
    np.testing.assert_allclose(homogeneous_series(p, ss, sigma=0.66), g / 2, rtol=1e-13, atol=1e-12)


def test_offcentre_independent_derivative():
    from scipy.special import eval_legendre

    ss = sensors(None)
    p = np.array([[0.03, 0.02, 0.01]])
    t = p[0] / 0.09
    u = ss / 0.09

    def potential(x):
        radius = np.linalg.norm(x)
        return sum(
            (2 * n + 1) / n * radius**n * eval_legendre(n, u @ x / radius) for n in range(1, 80)
        )

    eps = 1e-6
    grad = np.column_stack(
        [
            (potential(t + np.eye(3)[j] * eps) - potential(t - np.eye(3)[j] * eps)) / (2 * eps)
            for j in range(3)
        ]
    ) / (4 * np.pi * 0.33 * 0.09**2)
    np.testing.assert_allclose(homogeneous_series(p, ss), grad, rtol=1e-7, atol=1e-6)
    np.testing.assert_allclose(
        homogeneous_series(p, ss, terms=64), homogeneous_series(p, ss), rtol=1e-12, atol=1e-8
    )


@pytest.mark.parametrize("kind", ["sign", "axes", "scale", "source_order", "reference"])
def test_physical_error_not_scalar_rescued(kind):
    g = np.random.default_rng(28).normal(size=(32, 12))
    g -= g.mean(axis=0)
    a = g.copy()
    if kind == "sign":
        a = -a
    if kind == "axes":
        a = a.reshape(32, 4, 3)[:, :, [1, 0, 2]].reshape(32, 12)
    if kind == "scale":
        a *= 1000
    if kind == "source_order":
        a = a[:, np.roll(np.arange(12), 3)]
    if kind == "reference":
        a -= a[:1]
    m = field_metrics(a, g)
    assert m["relative"] > 0.1
    if kind == "sign":
        assert m["relative"] == pytest.approx(2.0)
        assert m["aligned_relative_diagnostic"] < 1e-12
    if kind == "scale":
        assert m["relative"] == pytest.approx(999.0)


@pytest.mark.parametrize("kind", ["outside", "sensor_radius", "sigma", "terms"])
def test_analytical_domain(kind):
    p = np.array([[0.02, 0.01, 0.03]])
    ss = sensors(None)
    kw = {}
    if kind == "outside":
        p *= 1000
    if kind == "sensor_radius":
        ss *= 1000
    if kind == "sigma":
        kw["sigma"] = 0.0
    if kind == "terms":
        kw["terms"] = 1
    with pytest.raises(ValueError):
        homogeneous_series(p, ss, **kw)


def test_oriented_triangle_correspondence():
    b = geometry(None, [1] * 3)[0]
    tri = b.vertices.xyz[b.faces]
    assert triangle_signature(tri) == triangle_signature(np.roll(tri, 1, axis=1))
    assert triangle_signature(tri) != triangle_signature(tri[:, [0, 2, 1]])


def test_corrupt_receipt():
    d = protocol().record()
    d["seal_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        SealedProtocol(canonical(d)).record()


def test_posthoc_threshold_rejected(tmp_path):
    from soma.experiments.bem_discrepancy import run_diagnostics

    d = protocol().protocol.document()
    d["optional_metadata"]["design"]["thresholds"]["independent_agreement"] = 0.2
    with pytest.raises(ValueError, match="protocol/threshold"):
        run_diagnostics(seal(Protocol.from_dict(d)), tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("kind", ["shape", "nan", "zero"])
def test_bad_operator(kind):
    g = np.ones((32, 6))
    a = g[:, :3] if kind == "shape" else g * np.nan if kind == "nan" else g * 0
    with pytest.raises(ValueError):
        field_metrics(a, g)


@pytest.mark.skipif(importlib.util.find_spec("openmeeg") is None, reason="optional conductor")
def test_independent_small_physics(tmp_path):
    b = geometry(None, [1] * 3)
    ss = sensors(None)
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.01, 0.01]])
    contracts = []
    exact = homogeneous_series(p, ss)
    exact -= exact.mean(axis=0)
    for solver in ["openmeeg", "mne"]:
        g, d = solve(b, p, ss, [0.33] * 3, tmp_path / solver, solver=solver)
        assert d["effective_geometry_unchanged"]
        assert d.get("sensor_projection_max_m", 0) < 1e-9
        assert field_metrics(g, exact)["relative"] < 0.4
        contracts.append(d["contracts"])
    match(*contracts)


def test_hierarchical_sources_not_components():
    from soma.experiments.nonspherical import hierarchical

    assert hierarchical(np.ones((6, 12))) == (1, 1, 1)
    with pytest.raises(ValueError):
        hierarchical(np.ones((18, 12)))
    with pytest.raises(ValueError):
        hierarchical(np.ones((6, 12)) * np.nan)


def test_native_roundtrip_and_restricted_identity(tmp_path):
    from soma.eeg_benchmark.evaluation import environment_snapshot
    from soma.experiments.bem_discrepancy import read_diagnostics
    from soma.results.contracts import create_result
    from soma.results.io import save_result

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

    def write(v, name):
        e = create_result(
            "experiment.manifest",
            domain,
            values=v,
            provenance={},
            method={"id": "soma.bem-discrepancy", "version": "1"},
            parameters={},
            units={},
            interpretation_state="DESCRIPTIVE_ONLY",
        )
        return save_result(e, {}, tmp_path / name)

    path = write(values, "valid")
    assert read_diagnostics(path) == values
    with pytest.raises(ValueError, match="identity"):
        read_diagnostics(write(dict(values, human_subjects=1), "human"))
    path.write_text(path.read_text().replace('"human_subjects":0', '"human_subjects":2'))
    with pytest.raises(ValueError):
        read_diagnostics(path)


def test_reviewed_explorer_identity():
    from services.explorer_api.source_uncertainty import bem_example

    v = bem_example()
    assert len(v["heads"]) == 6 and len(v["controls"]) == 2
    assert v["threshold"] == 0.1 and v["synthetic_only"] and v["human_subjects"] == 0
    assert not v["gates"]["INDEPENDENT_THREE_LAYER_AGREEMENT_PASS"]


@pytest.mark.parametrize(
    "problem", ["missing", "duplicate", "negative", "nan", "false_convergence"]
)
def test_false_refinement_acceptance_rejected(problem):
    from scripts.summarize_bem_discrepancy import refinement_accepts

    rows = [
        dict(head=h, solver=s, coarse=lev, fine=lev + 1, relative=0.2 if lev == 1 else 0.05)
        for h in range(6)
        for s in ["openmeeg", "mne"]
        for lev in [1, 2]
    ]
    assert refinement_accepts(rows)
    if problem == "missing":
        rows.pop()
    if problem == "duplicate":
        rows.append(dict(rows[0]))
    if problem == "negative":
        rows[0]["relative"] = -0.2
    if problem == "nan":
        rows[0]["relative"] = float("nan")
    if problem == "false_convergence":
        rows[1]["relative"] = 0.19
    assert not refinement_accepts(rows)


@pytest.mark.parametrize(
    "claim", [("four_layer", "PASS"), ("FEM", "PERFORMED"), ("phantom", "MEASURED")]
)
def test_inappropriate_independent_evidence_rejected(tmp_path, claim):
    from soma.eeg_benchmark.evaluation import environment_snapshot
    from soma.experiments.bem_discrepancy import read_diagnostics
    from soma.results.contracts import create_result
    from soma.results.io import save_result

    v = dict(
        synthetic_only=True,
        human_subjects=0,
        design_sha256=DESIGN_SHA,
        protocol_fingerprint=protocol().protocol.fingerprint,
    )
    v[claim[0]] = claim[1]
    domain = dict(
        computation="synthetic",
        inputs={},
        environment=environment_snapshot(),
        assumptions=[],
        validation={},
        limitations=["test"],
    )
    e = create_result(
        "experiment.manifest",
        domain,
        values=v,
        provenance={},
        method={"id": "soma.bem-discrepancy", "version": "1"},
        parameters={},
        units={},
        interpretation_state="DESCRIPTIVE_ONLY",
    )
    p = save_result(e, {}, tmp_path / "result")
    with pytest.raises(ValueError, match="evidence claim"):
        read_diagnostics(p)


def test_conductor_declaration_and_summary_units_match_actual_design():
    d = protocol().protocol.document()
    assert d["scientific"]["source_conductivity"]["sigmas_S_m"] == design()["conductivities_S_m"]
    assert d["scientific"]["source_conductivity"]["independent_four_layer"] == "NOT_ESTABLISHED"
    assert set(d["tolerances"]["axes"]) == {
        "models_computed",
        "models_failed",
        "inverse_rows",
        "inverse_computed",
        "source_count_per_head",
        "heads",
    }
    assert d["tolerances"]["units"] == ["1"] * 6
    assert d["amendment"]["outcome_inspection"] == "yes"


def test_inherited_four_layer_descriptor_rejected(monkeypatch):
    from types import SimpleNamespace

    import soma.source.bem_discrepancy as module

    d = protocol().protocol.document()
    d["scientific"]["source_conductivity"]["sigmas_S_m"] = [0.33, 1.0, 0.004, 0.33]
    bad = canonical(seal(Protocol.from_dict(d)).record()).decode()
    real = module.files
    monkeypatch.setattr(
        module,
        "files",
        lambda package: SimpleNamespace(
            joinpath=lambda name: (
                SimpleNamespace(read_text=lambda: bad)
                if name == "bem-discrepancy-protocol-v28-r3.json"
                else real(package).joinpath(name)
            )
        ),
    )
    with pytest.raises(ValueError, match="Conductor declaration"):
        module.protocol()
