import mne
import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

from soma.experiments.source_uncertainty import aggregate, known_truth, source_metrics
from soma.geometry import Frame, Points
from soma.protocol.model import Protocol, seal
from soma.source.inverse import CorticalInverse
from soma.source.uncertainty import (
    candidate_grid,
    check_protocol,
    design,
    electrode_positions,
    kernels,
    physical_forward,
    protocol,
    scenarios,
    transform,
)


@pytest.fixture(scope="module")
def forward():
    return physical_forward(candidate_grid(), electrode_positions(), transform())


def test_frozen_design_and_no_inverse_crime():
    p = protocol()
    check_protocol(p)
    assert len(scenarios()) == 49
    assert len({s["id"] for s in scenarios()}) == 49
    assert sum(s["family"] == "interaction" for s in scenarios()) == 15
    grid = candidate_grid().xyz
    truth, moments = known_truth()
    assert truth.xyz.shape == (12, 3)
    assert np.min(np.linalg.norm(grid[:, None] - truth.xyz[None], axis=2)) > 1e-6
    assert_allclose(np.linalg.norm(moments, axis=1), 1e-8, atol=1e-20)
    assert_allclose(known_truth()[0].xyz, truth.xyz)


def test_no_frozen_protocol_amendment():
    d = protocol().protocol.document()
    d["optional_metadata"]["design"]["seed"] += 1
    with pytest.raises(ValueError, match="drift"):
        check_protocol(seal(Protocol.from_dict(d)))


@pytest.mark.parametrize("mm,deg", [(0, 0), (5, 0), (0, 5), (-5, -5)])
def test_transform_direction(mm, deg):
    t = transform(mm, deg)
    p = Points(np.array([[0.02, 0.03, 0.04]]), Frame.HEAD)
    assert_allclose(t.inverse().apply(t.apply(p)).xyz, p.xyz, atol=1e-16)
    if deg == 0:
        assert_allclose(t.apply(p).xyz - p.xyz, [[mm / 1000, 0, 0]], atol=1e-16)
    if mm or deg:
        assert not np.allclose(t.apply(p).xyz, t.inverse().apply(Points(p.xyz, Frame.MRI)).xyz)


@pytest.mark.parametrize("rms", [0, 2, 5, 10])
def test_physical_electrode_rms_and_units(rms):
    delta = electrode_positions(rms).xyz - electrode_positions().xyz
    assert np.sqrt(np.mean(np.sum(delta**2, axis=1))) * 1000 == pytest.approx(rms, abs=1e-12)
    assert_allclose(
        Points.from_mm(candidate_grid().xyz * 1000, Frame.MRI).xyz, candidate_grid().xyz
    )
    with pytest.raises(ValueError, match="metres"):
        Points(candidate_grid().xyz, Frame.MRI, "mm")


@pytest.mark.parametrize(
    "fault",
    [
        "source_frame",
        "electrode_frame",
        "inverse_transform",
        "radii",
        "negative_sigma",
        "nan_sigma",
        "source_outside",
        "sensor_inside",
    ],
)
def test_invalid_physical_inputs(fault):
    points, electrodes, t = candidate_grid(), electrode_positions(), transform()
    radii, sigmas = list(design()["shell_radii_mm"]), list(design()["conductivities_S_m"])
    if fault == "source_frame":
        points = Points(points.xyz, Frame.HEAD)
    if fault == "electrode_frame":
        electrodes = Points(electrodes.xyz, Frame.MRI)
    if fault == "inverse_transform":
        t = t.inverse()
    if fault == "radii":
        radii[2] = radii[1]
    if fault == "negative_sigma":
        sigmas[2] = -0.1
    if fault == "nan_sigma":
        sigmas[2] = np.nan
    if fault == "source_outside":
        points = Points(points.xyz * 3, Frame.MRI)
    if fault == "sensor_inside":
        electrodes = Points(electrodes.xyz * 0.5, Frame.HEAD)
    with pytest.raises(ValueError):
        physical_forward(points, electrodes, t, radii, sigmas)


def test_real_conductivity_and_reference(forward):
    c = design()
    changed = physical_forward(
        candidate_grid(), electrode_positions(), transform(), sigmas=[0.33, 1, 0.01, 0.33]
    )
    assert np.linalg.norm(changed.matrix - forward.matrix) / np.linalg.norm(forward.matrix) > 0.01
    assert_allclose(forward.matrix.sum(axis=0), 0, atol=1e-12)
    assert forward.diagnostics["rank"] == c["sensors"] - 1
    assert forward.diagnostics["sphere_fit_rv"] < c["sphere_fit_max_rv"]
    shifted = physical_forward(candidate_grid(), electrode_positions(), transform(5, 0))
    assert not np.allclose(shifted.matrix, forward.matrix)
    outer = list(c["shell_radii_mm"])
    outer[2] += 1
    boundary = physical_forward(candidate_grid(), electrode_positions(), transform(), outer)
    assert not np.allclose(boundary.matrix, forward.matrix)


def test_independent_inverse_and_mne_application(forward):
    operators, check = kernels(forward, float(np.linalg.norm(forward.matrix, 2)))
    assert check["svd_vs_independent_solve_relative"] < 1e-10
    cov = mne.Covariance(
        5e-8**2 * forward.projector, forward.info["ch_names"], [], forward.info["projs"], nfree=1000
    )
    inv = CorticalInverse(forward, cov, lambda2=1 / 9, method="MNE", depth=None, orientation="free")
    y = np.random.default_rng(1).normal(size=(32, 2)) * 1e-7
    stc = inv.apply(mne.EvokedArray(y, forward.info.copy(), nave=1))
    assert_allclose(operators["MNE"] @ y, stc.data.reshape(144, 2), rtol=1e-10, atol=1e-22)
    with pytest.raises(ValueError):
        forward.require_vertices([np.arange(10)])
    with pytest.raises(ValueError):
        kernels(forward, np.nan)


def test_known_distance_dispersion_and_dimensionless_bias():
    grid = Points(np.array([[0.0, 0, 0], [0.03, 0, 0]]), Frame.MRI)
    truth = Points(np.array([[0.0, 0, 0]]), Frame.MRI)
    estimate = np.array([0, 0, 0, 1e-8, 0, 0])
    r = source_metrics(estimate, grid, truth, 0, "MNE")
    assert r["localization_mm"] == pytest.approx(30)
    assert r["dispersion_mm"] == pytest.approx(30)
    assert r["peak_amplitude_bias_ratio"] == pytest.approx(0)
    assert source_metrics(estimate, grid, truth, 0, "dSPM")["peak_amplitude_bias_ratio"] is None
    with pytest.raises(ValueError):
        source_metrics(estimate, grid, truth, 1, "MNE")
    with pytest.raises(ValueError):
        source_metrics(estimate, grid, Points(truth.xyz, Frame.HEAD), 0, "MNE")
    with pytest.raises(ValueError):
        source_metrics(estimate * 0, grid, truth, 0, "MNE")


def rows():
    return pd.DataFrame(
        [
            {
                "scenario": "baseline",
                "family": "baseline",
                "method": "Tikhonov",
                "noise_std_V": 5e-8,
                "draw": draw,
                "source": source,
                "status": "computed",
                "localization_mm": float(source),
                "dispersion_mm": 20.0,
                "peak_amplitude_bias_ratio": -0.5,
            }
            for source in range(12)
            for draw in range(8)
        ]
    )


def test_cluster_aggregation_and_retained_missingness():
    r = aggregate(rows())
    assert len(r) == 49 * 3 * 3
    complete = r[r.status == "complete"]
    assert len(complete) == 1
    assert complete.iloc[0].localization_mm == pytest.approx(5.5)
    assert complete.iloc[0].excess_localization_mm == 0
    assert complete.iloc[0].independent_generators == 12
    assert len(aggregate(rows().iloc[1:]).query("status == 'complete'")) == 0
    failed = rows()
    failed.loc[0, "status"] = "FAILED"
    assert len(aggregate(failed).query("status == 'complete'")) == 0


@pytest.mark.parametrize("fault", ["duplicate", "source", "draw", "method", "noise", "scenario"])
def test_invalid_uncertainty_pairings(fault):
    d = rows()
    if fault == "duplicate":
        d = pd.concat([d, d.iloc[:1]])
    if fault == "source":
        d.loc[0, "source"] = 100
    if fault == "draw":
        d.loc[0, "draw"] = 100
    if fault == "method":
        d.loc[0, "method"] = "tuned"
    if fault == "noise":
        d.loc[0, "noise_std_V"] = 10
    if fault == "scenario":
        d.loc[0, "scenario"] = "unplanned"
    with pytest.raises(ValueError):
        aggregate(d)


def test_solver_failure_propagates_without_fabricated_result(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injected numerical solver failure")

    monkeypatch.setattr(mne, "make_forward_solution", fail)
    with pytest.raises(RuntimeError, match="solver failure"):
        physical_forward(candidate_grid(), electrode_positions(), transform())


@pytest.mark.parametrize("fault", ["checksum", "human", "protocol", "design"])
def test_native_result_corruption(tmp_path, fault):
    import json

    from soma.experiments.source_uncertainty import read_uncertainty
    from soma.results.contracts import create_result
    from soma.results.io import save_result
    from soma.source.uncertainty import DESIGN_SHA256

    values = {
        "synthetic_only": True,
        "human_subjects": 0,
        "design_sha256": DESIGN_SHA256,
        "protocol_fingerprint": protocol().protocol.fingerprint,
    }
    if fault == "human":
        values["synthetic_only"] = False
    if fault == "protocol":
        values["protocol_fingerprint"] = "a" * 64
    if fault == "design":
        values["design_sha256"] = "a" * 64
    domain = {
        "computation": "test",
        "inputs": {},
        "environment": {},
        "assumptions": ["synthetic"],
        "validation": {"scope": "numerical"},
        "limitations": ["not human"],
    }
    result = create_result(
        "experiment.manifest",
        domain,
        values=values,
        provenance={},
        method={"id": "soma.source-uncertainty", "version": "1"},
        parameters={},
        units={},
    )
    save_result(result, {}, tmp_path / "artifact")
    path = tmp_path / "artifact/result.json"
    if fault == "checksum":
        d = json.loads(path.read_text())
        d["payload"]["values"]["human_subjects"] = 99
        path.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        read_uncertainty(path)


def test_explorer_serves_only_executed_synthetic_examples():
    from fastapi.testclient import TestClient

    from services.explorer_api.app import create_app

    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get("/api/source-uncertainty")
        assert response.status_code == 200
        d = response.json()
        assert d["synthetic_only"] and d["human_subjects"] == 0
        assert d["configurations"] == 49 and len(d["failed_configurations"]) == 9
        assert len(d["examples"]) == 18
        assert d["protocol_fingerprint"] == protocol().protocol.fingerprint
        assert all(
            e["metrics"]["peak_amplitude_bias_ratio"] is None
            for e in d["examples"]
            if e["method"] == "dSPM"
        )
        assert client.post("/api/source-uncertainty", json={"execute": True}).status_code == 405
