import itertools
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose
from typer.testing import CliRunner

from soma.cli import app
from soma.reliability.config import configuration, stream
from soma.reliability.workflows import interaction, paired_interval


def test_factorial_interactions_exact_polynomial_oracle():
    common = np.arange(10.0) * 0.01
    cells = {}
    for a, b, c in itertools.product((0, 1), repeat=3):
        cells[a, b, c] = common + 2 * a + 3 * b + 4 * c + 5 * a * b + 7 * a * c + 9 * a * b * c
    assert_allclose(interaction(cells, (0, 1)), 5)
    assert_allclose(interaction(cells, (0, 2)), 7)
    assert_allclose(interaction(cells, (1, 2)), 0, atol=1e-14)
    assert_allclose(interaction(cells, (0, 1, 2)), 9)
    with pytest.raises(ValueError):
        interaction(cells, (0, 0))


def test_paired_simulation_streams_and_intervals():
    a = stream(42, 1).normal(size=100)
    b = stream(42, 1).normal(size=100)
    assert_allclose(a, b, atol=0, rtol=0)
    assert not np.array_equal(a, stream(42, 2).normal(size=100))
    paired = paired_interval((a + 0.2) - b)
    assert_allclose(paired["mean"], 0.2)
    independent = paired_interval(a + 0.2 - stream(42, 2).normal(size=100))
    assert independent["high95"] - independent["low95"] > paired["high95"] - paired["low95"]
    with pytest.raises(ValueError):
        paired_interval([1])


@pytest.mark.parametrize(
    "command", ["audit-coreg", "audit-inverse", "resolution-study", "uncertainty-study"]
)
def test_new_source_cli_offline_help(command):
    assert CliRunner().invoke(app, ["source", command, "--help"]).exit_code == 0


def test_anatomy_evidence_cli_and_no_implicit_download(tmp_path, monkeypatch):
    import mne

    assert CliRunner().invoke(app, ["anatomy", "audit-evidence", "--help"]).exit_code == 0

    def forbidden(*args, **kwargs):
        raise AssertionError("Implicit fetch")

    monkeypatch.setattr(mne.datasets.sample, "data_path", forbidden)
    result = CliRunner().invoke(
        app, ["source", "audit-coreg", "--dataset", "unknown", "--output", str(tmp_path / "new")]
    )
    assert result.exit_code == 1
    assert "matched MNE sample" in result.output
    assert not (tmp_path / "new").exists()


def test_frozen_reliability_configuration():
    from importlib.metadata import version

    import soma

    assert version("soma-neuro") == soma.__version__
    assert configuration(Path("configs/inverse-audit.yaml"))["seed"] == 42
    with pytest.raises(ValueError):
        configuration(Path("configs/individual-source.yaml"))
