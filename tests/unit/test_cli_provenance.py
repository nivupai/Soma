import json

import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.core.provenance import output_directory, write_json
from soma.signal.experiments import synthetic_spectrum

runner = CliRunner()


def test_cli_help_list_and_errors(tmp_path):
    for args in (
        ["--help"],
        ["datasets", "list"],
        ["eeg", "--help"],
        ["experiments", "synthetic-spectrum", "--help"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(app, ["eeg", "inspect", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "Missing EDF" in result.output
    assert runner.invoke(app, ["datasets", "fetch", "eegmmidb"]).exit_code == 2


def test_no_overwrite_and_strict_json(tmp_path):
    with pytest.raises(FileExistsError):
        output_directory(tmp_path)
    path = tmp_path / "test.json"
    write_json(path, {"valid": True})
    with pytest.raises(FileExistsError):
        write_json(path, {})


def test_synthetic_artifacts(tmp_path):
    output = tmp_path / "lab"
    synthetic_spectrum(output, seed=19)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["random_seed"] == 19
    assert manifest["parameters"]["fs_hz"] == 160
    assert manifest["libraries"]["neurodsp"] == "2.3.0"
    for name in ("psd.png", "signals.png", "summary.csv", "spectra.npz", "report.md"):
        assert (output / name).stat().st_size > 50
    with pytest.raises(FileExistsError):
        synthetic_spectrum(output)
