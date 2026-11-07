from pathlib import Path

import mne
import numpy as np
import pytest
from numpy.testing import assert_allclose
from typer.testing import CliRunner

from soma.cli import app
from soma.source.template import Template
from soma.source.workflow import sealed_config


def test_missing_assets_never_fetch(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network fetch attempted")

    monkeypatch.setattr(mne.datasets, "fetch_fsaverage", forbidden)
    with pytest.raises(FileNotFoundError, match="explicitly"):
        Template(tmp_path).inspect()
    result = CliRunner().invoke(
        app, ["source", "inspect-template", "--template-dir", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "Missing template assets" in result.output


@pytest.mark.parametrize(
    "command", ["inspect-template", "forward", "simulate", "inverse", "resolution"]
)
def test_source_cli_help(command):
    result = CliRunner().invoke(app, ["source", command, "--help"])
    assert result.exit_code == 0


def test_protocol_is_sealed():
    for path in Path("configs").glob("source-*.yaml"):
        assert sealed_config(path)


@pytest.mark.integration
def test_actual_template_forward_inverse():
    from soma.source.inverse import CorticalInverse
    from soma.source.workflow import study_forward, synthetic_covariance

    if not Template().bem.exists():
        pytest.skip("Explicitly cached fsaverage required; test never fetches")
    forward = study_forward()
    assert forward.matrix.shape == (64, 1284)
    assert forward.diagnostics()["rank"] == 63
    assert forward.geometry["max_distance_m"] < 0.003
    _, covariance = synthetic_covariance(forward, seed=8)
    for orientation in ("fixed", "free"):
        inverse = CorticalInverse(forward, covariance, orientation=orientation)
        rng = np.random.default_rng(8)
        y = forward.projector @ rng.normal(size=(64, 20)) * 1e-6
        stc = inverse.apply(mne.EvokedArray(y, forward.info.copy(), nave=1))
        forward.require_vertices(stc.vertices)
        if orientation == "fixed":
            expected = stc.data
        else:
            expected = np.einsum(
                "nij,njk->nik", forward.native_free["source_nn"].reshape(-1, 3, 3), stc.data
            ).reshape(-1, 20)
        assert_allclose(inverse.kernel @ y, expected, atol=1e-20, rtol=1e-10)
        assert inverse.units == "A m"
    dspm = CorticalInverse(forward, covariance, method="dSPM")
    assert dspm.units == "dimensionless"
    assert np.isfinite(dspm.kernel).all()
    with pytest.raises(ValueError):
        dspm.apply(mne.EvokedArray(y, forward.info.copy(), nave=2))


@pytest.mark.integration
def test_mne_whitener_and_covariance_boundary():
    from soma.source.inverse import CorticalInverse
    from soma.source.workflow import study_forward, synthetic_covariance

    if not Template().bem.exists():
        pytest.skip("Explicitly cached anatomy required")
    forward = study_forward()
    noise, covariance = synthetic_covariance(forward, seed=9)
    q, _ = mne.cov.compute_whitener(covariance, forward.info, rank={"eeg": 63}, verbose=False)
    assert_allclose(q @ noise.covariance @ q.T, forward.projector, atol=1e-11)
    bad = covariance.copy()
    bad["projs"] = []
    with pytest.raises(ValueError, match="projector"):
        CorticalInverse(forward, bad)
    bad = covariance.copy()
    bad["names"] = bad["names"][::-1]
    with pytest.raises(ValueError, match="ordering"):
        CorticalInverse(forward, bad)


@pytest.mark.integration
def test_fresh_cached_forward_and_corruption_detection(tmp_path):
    from soma.source.forward import build_forward
    from soma.source.workflow import study_forward

    if not Template().bem.exists():
        pytest.skip("Explicitly cached anatomy required")
    cached = study_forward()
    fresh = build_forward(Template(), cached.info.ch_names)
    assert_allclose(cached.matrix, fresh.matrix, rtol=5e-5, atol=2e-5)
    assert cached.coordinates.identifiers == fresh.coordinates.identifiers
    # The cache checksum is checked before attempting to parse the FIF payload.
    path = tmp_path / "corrupt-fwd.fif"
    path.write_bytes(b"not a forward")
    original = Path("data/derived/source/fsaverage-ico3-fwd.json")
    path.with_suffix(".json").write_text(original.read_text())
    with pytest.raises(ValueError, match="cache identity"):
        build_forward(Template(), cached.info.ch_names, cache=path)


@pytest.mark.integration
def test_mne_simulation_matches_referenced_lead_field():
    from soma.source.workflow import study_forward

    if not Template().bem.exists():
        pytest.skip("Explicitly cached anatomy required")
    forward = study_forward()
    currents = np.zeros((forward.matrix.shape[1], 100))
    currents[123] = 1e-8 * np.sin(np.arange(100) * 0.2)
    stc = mne.SourceEstimate(currents, forward.vertices, 0, 1 / 160, subject="fsaverage")
    evoked = mne.simulation.simulate_evoked(
        forward.native_fixed, stc, forward.info.copy(), cov=None, use_cps=False, verbose=False
    )
    assert_allclose(evoked.data, forward.unreferenced @ currents, atol=1e-18, rtol=1e-10)
    # MNE explicitly removes input projections when generating noiseless evoked data.
    evoked.add_proj(forward.info["projs"], verbose=False).apply_proj(verbose=False)
    assert_allclose(evoked.data, forward.matrix @ currents, atol=1e-18, rtol=1e-10)
