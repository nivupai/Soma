import json

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.eeg.motor_imagery import MotorImageryConfig, analyze_run, motor_imagery
from soma.eeg.preprocessing import PreprocessingConfig
from soma.signal.event_locked import event_locked_eeg


def test_event_locked_workflow_artifacts(tmp_path):
    output = tmp_path / "lab"
    cfg = MotorImageryConfig(preprocessing=PreprocessingConfig(reference="none"), plots=False)
    m = motor_imagery(tmp_path, 1, [4], output, cfg, synthetic_seed=12, synthetic_artifacts=True)
    assert m["random_seed"] == 12
    for name in (
        "events.csv",
        "trials.csv",
        "quality.json",
        "spectral_features.csv",
        "condition_summary.csv",
        "preprocessing.json",
        "manifest.json",
        "geometry.json",
        "lateralization.csv",
        "report.md",
        "synthetic_truth.json",
    ):
        assert (output / name).stat().st_size > 0
    with np.load(output / "run-04" / "timefrequency.npz", allow_pickle=False) as arrays:
        assert arrays["power"].ndim == 4
        assert arrays["channels"].tolist() == ["C3", "Cz", "C4"]
    q = json.loads((output / "quality.json").read_text())["4"]
    assert q["trial_counts"]["analysis"]["rejected"] >= 1
    df = pd.read_csv(output / "trials.csv")
    assert df.rejection_reasons.notna().any()
    with pytest.raises(FileExistsError):
        motor_imagery(tmp_path, 1, [4], output, cfg, synthetic_seed=12)


def test_no_valid_rest_masks_normalization():
    raw, _ = event_locked_eeg()
    cfg = MotorImageryConfig(
        preprocessing=PreprocessingConfig(reference="none"), minimum_rest_s=10, plots=False
    )
    result = analyze_run(raw, 1, 4, "model", cfg)
    assert np.isnan(result["band_change"].percent).all()
    assert np.isnan(result["tfr_change"].percent).all()
    assert np.isfinite(result["features"].absolute_power_v2).all()
    with pytest.raises(ValueError):
        analyze_run(raw, 1, 6, "bilateral", cfg)


def test_multi_run_identity_never_pooled(tmp_path, monkeypatch):
    from soma.core.provenance import sha256
    from soma.eeg import motor_imagery as module

    fake = tmp_path / "synthetic.edf"
    fake.write_bytes(b"identity fixture only; loader returns synthetic Raw")

    def load(root, subject, run):
        raw, _ = event_locked_eeg()
        return raw, {
            "dataset": "fixture",
            "file_identifier": f"S001R{run:02d}.edf",
            "subject": subject,
            "run": run,
            "sha256": sha256(fake),
        }

    monkeypatch.setattr(module, "load_recording", load)
    monkeypatch.setattr(module, "recording_path", lambda *args: fake)
    output = tmp_path / "multi"
    module.motor_imagery(tmp_path, 1, [4, 8, 12], output, MotorImageryConfig(plots=False))
    for name in ("events.csv", "trials.csv", "spectral_features.csv", "condition_summary.csv"):
        table = pd.read_csv(output / name)
        assert set(table.run) == {4, 8, 12}
    assert len(json.loads((output / "manifest.json").read_text())["source"]["recordings"]) == 3


def test_cli_new_help_errors_and_synthetic(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["eeg", "motor-imagery", "--help"]).exit_code == 0
    assert runner.invoke(app, ["experiments", "event-locked", "--help"]).exit_code == 0
    result = runner.invoke(
        app, ["eeg", "motor-imagery", "--runs", "6", "--output", str(tmp_path / "bad")]
    )
    assert result.exit_code == 1
    assert "4, 8, 12" in result.output
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"baseline": "none", "preprocessing": {"reference": "none"}}))
    result = runner.invoke(
        app,
        [
            "experiments",
            "event-locked",
            "--output",
            str(tmp_path / "cli"),
            "--no-plots",
            "--config",
            str(config),
        ],
    )
    assert result.exit_code == 0, result.output
    summary = pd.read_csv(tmp_path / "cli" / "condition_summary.csv")
    assert summary.mean_erd_percent.isna().all()


def test_all_trials_rejected_preserves_schema_and_optional_plot_mask(tmp_path):
    from soma.eeg.quality import QualityConfig

    output = tmp_path / "empty"
    cfg = MotorImageryConfig(quality=QualityConfig(trial_ptp_v=1e-12), plots=False)
    motor_imagery(tmp_path, 1, [4], output, cfg, synthetic_seed=42)
    summary = pd.read_csv(output / "condition_summary.csv")
    assert summary.empty and "mean_power_v2" in summary
    assert pd.read_csv(output / "lateralization.csv").empty
    q = json.loads((output / "quality.json").read_text())["4"]
    assert q["trial_counts"]["analysis"] == {"proposed": 8, "accepted": 0, "rejected": 8}
    with np.load(output / "run-04" / "timefrequency.npz", allow_pickle=False) as a:
        assert a["power"].shape == (0, 3, 23, 640)
        assert np.isnan(a["condition_mean_power"]).all()


def test_plot_workflow_without_reference_does_not_create_erd(tmp_path):
    output = tmp_path / "no-reference"
    cfg = MotorImageryConfig(baseline="none", plots=True)
    motor_imagery(tmp_path, 1, [4], output, cfg, synthetic_seed=42)
    for name in (
        "sensor_montage.png",
        "event_timeline.png",
        "psd_comparison.png",
        "timefrequency.png",
    ):
        assert (output / name).stat().st_size > 1000
    assert not (output / "erd_ers.png").exists()
