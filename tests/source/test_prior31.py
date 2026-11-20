"""Independent analytical and adversarial checks for moment-prior calibration."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import (
    PriorInverse,
    SourcePrior,
    amplitude_unit,
    cell_volumes,
    conditional_interval,
    positions,
    source_split,
)


def setup():
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0], [-0.02, 0.0, 0.0]])
    g = average_projector(5) @ np.arange(45).reshape(5, 9).astype(float)
    # Nontrivial rank, not just a rank-one arithmetic progression.
    g += average_projector(5) @ np.random.default_rng(31).normal(size=(5, 9))
    c = (5e-8) ** 2 * average_projector(5)
    noise = NoiseModel(c, tuple("abcde"), average_projector(5))
    return p, g, noise


@pytest.mark.parametrize("kind", ["unweighted", "cell_volume", "total_variance"])
def test_covariance_and_continuous_mass(kind):
    p, g, n = setup()
    v = cell_volumes(p)
    prior = SourcePrior.create(p, kind, v)
    assert np.isclose(v.sum(), 4 * np.pi * 0.065**3 / 3, rtol=1e-14)
    # Independent analytical ball/slab integral checks the approximate cell masses.
    central = 3 * 0.01 / (2 * 0.065) - 0.01**3 / (2 * 0.065**3)
    exact = np.array([central, (1 - central) / 2, (1 - central) / 2])
    assert np.max(np.abs(v / v.sum() - exact)) < 5e-4
    assert np.all(prior.diagonal > 0) and not prior.diagonal.flags.writeable
    assert np.isclose(prior.trace_Am2, (9 if kind == "unweighted" else 36) * 1e-16, rtol=1e-12)
    if kind == "cell_volume":
        q = 12 * 1e-16 / v.sum()
        assert np.allclose(prior.diagonal[::3] * 1e-16, q * v, rtol=1e-12, atol=0)
    assert np.linalg.norm(n.whitener @ n.covariance @ n.whitener.T - np.eye(4)) < 1e-12


@pytest.mark.parametrize("method", ["Tikhonov", "MNE", "dSPM"])
def test_independent_normal_equations_and_noise_normalization(method):
    p, g, n = setup()
    pr = SourcePrior.create(p, "cell_volume")
    inv = PriorInverse(g, p, pr, n, method)
    a, r, b = inv.components()
    alpha = 0.17
    # Independently solve coefficient-space normal equations rather than sensor-space formula.
    expected = (
        np.linalg.solve(a.T @ a + alpha * np.diag(1 / r), a.T) @ n.whitener * pr.moment_scale_Am
    )
    k = inv.kernel(alpha, physical=True)
    assert np.allclose(k, expected, rtol=1e-9, atol=1e-14)
    if method != "Tikhonov":
        assert np.isclose(np.trace(b), 4, rtol=1e-12)
    if method == "dSPM":
        ds = inv.kernel(alpha)
        block = np.einsum("ij,jk,ik->i", ds, n.covariance, ds).reshape(-1, 3).sum(axis=1)
        assert np.allclose(block, 1, rtol=1e-12)


@pytest.mark.parametrize(
    "fault", ["negative", "zero", "nan", "volume", "unit", "orientation", "diagonal"]
)
def test_bad_prior_rejected(fault):
    p, _, _ = setup()
    pr = SourcePrior.create(p, "cell_volume")
    if fault in ("negative", "zero", "nan", "diagonal"):
        d = pr.diagonal.copy()
        d[0] = {"negative": -1.0, "zero": 0.0, "nan": np.nan, "diagonal": 100.0}[fault]
        change = {"diagonal": d}
    elif fault == "volume":
        change = {"volumes_m3": pr.volumes_m3 * 2}
    elif fault == "unit":
        change = {"coefficient_unit": "A/m^2"}
    else:
        change = {"orientation_order": "XYZ-major"}
    with pytest.raises(ValueError):
        replace(pr, **change)


@pytest.mark.parametrize(
    "bad", [np.zeros((2, 3)), np.array([[0.1, 0, 0]]), np.array([[np.nan, 0, 0]]), np.zeros((1, 2))]
)
def test_invalid_positions(bad):
    with pytest.raises(ValueError):
        positions(bad)


def test_order_split_amplitude_and_aggregation_guards():
    p, g, n = setup()
    pr = SourcePrior.create(p, "total_variance")
    with pytest.raises(ValueError):
        PriorInverse(g, p[::-1], pr, n, "MNE")
    with pytest.raises(ValueError):
        source_split([0, 1], [1, 2], 3)
    with pytest.raises(ValueError):
        source_split([0], [2], 3)
    source_split([0], [1, 2], 3)
    with pytest.raises(ValueError):
        amplitude_unit("dSPM", True)
    with pytest.raises(ValueError):
        conditional_interval(np.ones(100))
    assert conditional_interval(np.ones((6, 4))) == (1.0, 1.0, 1.0)


def test_regularization_scaling_and_repeat_selection():
    p, g, n = setup()
    inv = PriorInverse(g, p, SourcePrior.create(p, "unweighted"), n, "MNE")
    y = average_projector(5) @ np.random.default_rng(2).normal(size=(5, 6)) * 1e-7
    sweep = np.linspace(-4, 4, 17)
    alpha, boundary, loss = inv.alpha("prediction", 100, sweep, y, y)
    assert len(loss) == 17 and np.isfinite(loss).all() and alpha > 0
    assert isinstance(boundary, bool)
    spectral = inv.alpha("spectral", 100, sweep, y, y)[0]
    assert np.isclose(inv.diagnostics(spectral)["alpha_over_top"], 1 / 9)
    # Selection API receives only calibration measurements, no test positions or errors.
    other = inv.alpha("prediction", 100, sweep, y, y)
    assert other == (alpha, boundary, loss)
    with pytest.raises(ValueError):
        inv.alpha("prediction", 100, sweep, y, y[:, :2])


def test_original_M30_integrity_and_frozen_new_design():
    original = json.loads(Path("experiments/milestone30/manifest.json").read_text())
    for name, expected in original.items():
        assert (
            hashlib.sha256((Path("experiments/milestone30") / name).read_bytes()).hexdigest()
            == expected
        )
    seal = json.loads(Path("experiments/milestone31/seal.json").read_text())
    assert (
        hashlib.sha256(Path("experiments/milestone31/design.json").read_bytes()).hexdigest()
        == seal["design_sha256"]
    )


def test_global_prior_scale_cancels_MNE_trace_normalization():
    p, g, n = setup()
    a = PriorInverse(g, p, SourcePrior.create(p, "unweighted"), n, "MNE")
    b = PriorInverse(g, p, SourcePrior.create(p, "total_variance"), n, "MNE")
    assert np.allclose(a.kernel(1 / 9), b.kernel(1 / 9), rtol=1e-11, atol=1e-14)


def test_misleading_cross_grid_resolution_rejected():
    from soma.source.grid_diagnostics import resolution_difference

    p, _, _ = setup()
    with pytest.raises(ValueError):
        resolution_difference(np.eye(9), np.eye(9), p, p[::-1], "1", "1")


def test_corrupted_and_incomplete_scientific_results(monkeypatch):
    from soma.source import prior_calibration as api

    raw = Path("src/soma/resources/inverse-calibration-example-v31.json").read_bytes()
    assert api.validate_example(raw)["synthetic_only"] is True
    with pytest.raises(ValueError, match="fingerprint"):
        api.validate_example(raw + b" ")
    v = json.loads(raw)
    v["receipt"]["failed_configurations"] = 1
    changed = json.dumps(v).encode()
    monkeypatch.setattr(api, "EXAMPLE_SHA256", hashlib.sha256(changed).hexdigest())
    with pytest.raises(ValueError, match="unreported"):
        api.validate_example(changed)


def test_API_read_only_frozen_results():
    from fastapi.testclient import TestClient

    from services.explorer_api.app import app

    client = TestClient(app, base_url="http://127.0.0.1")
    r = client.get("/api/inverse-calibration")
    assert r.status_code == 200 and r.json()["receipt"]["new_heldout_sources"] == 24
    assert client.post("/api/inverse-calibration", json={}).status_code == 405


def test_mutation_and_zero_lead_guards():
    p, g, n = setup()
    inv = PriorInverse(g, p, SourcePrior.create(p, "cell_volume"), n, "MNE")
    expected = inv.kernel(0.1)
    g[:] = 0
    p[:] = 0
    assert np.array_equal(inv.kernel(0.1), expected)
    p, g, n = setup()
    with pytest.raises(ValueError):
        PriorInverse(g * 0, p, SourcePrior.create(p, "cell_volume"), n, "MNE")


def test_small_cross_platform_reference_and_missing_reports(tmp_path):
    from scripts.compare_prior_calibration import compare
    from scripts.prior_calibration_repro import run

    r = run()
    with pytest.raises(ValueError, match="Four"):
        compare(tmp_path)
    for i, (os, arch, py) in enumerate(
        (os, arch, py)
        for os, arch in [("Linux", "x86_64"), ("Darwin", "arm64")]
        for py in ["3.11.0", "3.12.0"]
    ):
        v = dict(r, environment=dict(system=os, machine=arch, python=py))
        d = tmp_path / str(i)
        d.mkdir()
        (d / "inverse-prior-synthetic.json").write_text(json.dumps(v))
    assert compare(tmp_path)["all_passed"] is True
    p = tmp_path / "3/inverse-prior-synthetic.json"
    v = json.loads(p.read_text())
    v["data"][0]["kernel"][0][0] += 1
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="numerical"):
        compare(tmp_path)
