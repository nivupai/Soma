import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.experiments.cache import canonical_id
from soma.experiments.cohort import run_cohort
from soma.experiments.config import CohortConfig, config_from_dict, read_config, scientific_dict
from soma.experiments.sensitivity import run_sensitivity, sensitivity_design


def test_config_yaml_roundtrip_and_identity(tmp_path):
    path = tmp_path / "cohort.yaml"
    path.write_text(
        "subjects: [2, 1]\nruns: [8, 4]\nplots: false\n"
        "motor:\n  preprocessing:\n    reference: channels\n    reference_channels: [Fz, Pz]\n"
    )
    cfg = config_from_dict(read_config(path))
    assert cfg.motor.preprocessing.reference_channels == ("Fz", "Pz")
    assert canonical_id(scientific_dict(cfg)) == canonical_id(
        scientific_dict(replace(cfg, subjects=(1, 2), runs=(4, 8)))
    )
    path.write_text("- wrong\n- shape\n")
    with pytest.raises(ValueError):
        read_config(path)
    with pytest.raises(TypeError):
        config_from_dict({"unknown": 1})


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(subjects=()),
        dict(subjects=(1, 1)),
        dict(runs=(4, 4)),
        dict(subjects=(0,)),
        dict(runs=(6,)),
        dict(dataset="unknown"),
    ],
)
def test_invalid_cohort_selection(kwargs):
    with pytest.raises(ValueError):
        CohortConfig(**kwargs)


def test_primary_design_is_manageable_and_predefined():
    design = sensitivity_design(CohortConfig())
    assert len(design) == 10
    base = asdict(design["primary"][1])
    for name, (reason, cfg) in design.items():
        assert reason
        if name == "primary":
            continue
        alternative = asdict(cfg)
        changed = [key for key in base if base[key] != alternative[key]]
        assert len(changed) == 1
    assert design["reference_fz_pz"][1].motor.preprocessing.reference_channels == ("Fz", "Pz")


def test_cohort_cache_reuse_grouping_and_corruption_report(tmp_path):
    cfg = CohortConfig(subjects=(1, 2), runs=(4,), synthetic_seed=42, plots=False)
    cache = tmp_path / "cache"
    cold = run_cohort(tmp_path, tmp_path / "cold", cfg, cache)
    warm = run_cohort(tmp_path, tmp_path / "warm", cfg, cache)
    assert cold["complete"] == warm["complete"] == 2
    assert cold["experiment_id"] == warm["experiment_id"]
    coverage = pd.read_csv(tmp_path / "warm" / "coverage.csv")
    assert coverage.cache_hit.all()
    assert not pd.read_csv(tmp_path / "cold" / "coverage.csv").cache_hit.any()
    frames = pd.read_csv(tmp_path / "warm" / "events.csv")
    assert set(frames.subject) == {1, 2}
    assert frames.groupby(["subject", "run", "recording"]).size().tolist() == [17, 17]
    table = pd.read_csv(tmp_path / "warm" / "subject_contrasts.csv")
    assert table.groupby(["subject", "channel", "band", "outcome"]).size().max() == 1
    key = coverage.iloc[0].cache_key
    (cache / key / "features.csv").write_text("corrupted")
    assert not run_cohort(tmp_path, tmp_path / "corrupt", cfg, cache)["status"] == "complete"
    failed = json.loads((tmp_path / "corrupt" / "coverage.json").read_text())["records"][0]
    assert "Corrupt cache artifact" in failed["error"]
    with pytest.raises(FileExistsError):
        run_cohort(tmp_path, tmp_path / "cold", cfg, cache)


def test_all_missing_cohort_has_explicit_failures(tmp_path):
    cfg = CohortConfig(subjects=(1, 2), runs=(4, 8), plots=False)
    result = run_cohort(tmp_path / "empty", tmp_path / "out", cfg, tmp_path / "cache")
    assert result["complete"] == 0 and result["failed"] == 4
    coverage = json.loads((tmp_path / "out" / "coverage.json").read_text())
    assert all(row["category"] == "missing" for row in coverage["records"])
    assert pd.read_csv(tmp_path / "out" / "features.csv").empty


def test_partial_failure_sampling_and_channel_compatibility(tmp_path, monkeypatch):
    from soma.experiments import cohort as module
    from soma.signal.cohort_synthetic import cohort_recording

    original = cohort_recording

    def inconsistent(subject, run, seed, **kwargs):
        if subject == 2:
            raise ValueError("deliberately incomplete annotation file")
        raw, truth = original(subject, run, seed, **kwargs)
        if run == 8:
            raw.drop_channels(["Pz"])
        return raw, truth

    monkeypatch.setattr(module, "cohort_recording", inconsistent)
    cfg = CohortConfig(subjects=(1, 2), runs=(4, 8), synthetic_seed=3, plots=False)
    result = run_cohort(tmp_path, tmp_path / "partial", cfg, tmp_path / "cache")
    assert result["complete"] == 1 and result["failed"] == 3
    coverage = json.loads((tmp_path / "partial" / "coverage.json").read_text())["records"]
    assert any("channel sets" in row.get("error", "") for row in coverage)
    subjects = pd.read_csv(tmp_path / "partial" / "subject_contrasts.csv")
    assert (subjects[subjects.subject == 2].n_runs == 0).all()
    assert subjects[subjects.subject == 2].contrast.isna().all()


def test_cache_parameter_invalidation(tmp_path):
    cfg = CohortConfig(subjects=(1,), runs=(4,), synthetic_seed=12, plots=False)
    cache = tmp_path / "cache"
    run_cohort(tmp_path, tmp_path / "base", cfg, cache)
    changed = replace(cfg, motor=replace(cfg.motor, baseline="none"))
    result = run_cohort(tmp_path, tmp_path / "changed", changed, cache)
    assert result["complete"] == 1
    assert not pd.read_csv(tmp_path / "changed" / "coverage.csv").cache_hit.any()
    frame = pd.read_csv(tmp_path / "changed" / "features.csv")
    assert frame.erd_percent.isna().all()
    assert len(list(cache.iterdir())) == 2


def test_sensitivity_retains_missingness_and_all_named_variants(tmp_path):
    cfg = CohortConfig(subjects=(1, 2), runs=(4,), synthetic_seed=11, plots=False)
    values = {"cohort": asdict(cfg), "variants": ["primary", "normalization_none", "qc_strict"]}
    result = run_sensitivity(tmp_path, tmp_path / "sweep", values, tmp_path / "cache")
    assert result["variants"] == 3
    missing = pd.read_csv(tmp_path / "sweep" / "sensitivity_missingness.csv").set_index("variant")
    assert missing.loc["normalization_none", "missing_reference_fraction"] == 1
    effects = pd.read_csv(tmp_path / "sweep" / "sensitivity_effects.csv")
    absolute = effects[
        (effects.variant == "normalization_none") & (effects.outcome == "log_absolute_power")
    ]
    np.testing.assert_allclose(absolute.effect_change, 0, atol=1e-12)
    with pytest.raises(ValueError):
        run_sensitivity(
            tmp_path,
            tmp_path / "bad",
            {"cohort": {}, "variants": ["best-looking"]},
            tmp_path / "cache",
        )


def test_new_cli_help_and_structured_all_missing_error(tmp_path):
    runner = CliRunner()
    for arguments in (
        ["eeg", "cohort"],
        ["eeg", "bursts"],
        ["eeg", "sensitivity"],
        ["experiments", "cohort-synthetic"],
        ["experiments", "benchmark"],
        ["experiments", "uncertainty-validation"],
    ):
        result = runner.invoke(app, arguments + ["--help"])
        assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "eeg",
            "cohort",
            "--subjects",
            "1",
            "--runs",
            "4",
            "--data-dir",
            str(tmp_path / "none"),
            "--output",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--no-plots",
        ],
    )
    assert result.exit_code == 1
    assert '"status": "failed"' in result.output


def test_sampling_rate_inconsistency_is_reported_without_resampling(tmp_path, monkeypatch):
    from soma.experiments import cohort as module
    from soma.signal.cohort_synthetic import cohort_recording

    def mismatched(subject, run, seed, **kwargs):
        raw, truth = cohort_recording(subject, run, seed, **kwargs)
        if run == 8:
            raw.resample(128, verbose=False)
        return raw, truth

    monkeypatch.setattr(module, "cohort_recording", mismatched)
    cfg = CohortConfig(subjects=(1,), runs=(4, 8), synthetic_seed=19, plots=False)
    result = run_cohort(tmp_path, tmp_path / "out", cfg, tmp_path / "cache")
    assert result["complete"] == 1
    rows = json.loads((tmp_path / "out" / "coverage.json").read_text())["records"]
    assert rows[1]["status"] == "failed"
    assert "sampling frequency" in rows[1]["error"]


def test_fixed_reference_channels_change_signal_without_mutation():
    from soma.eeg.preprocessing import PreprocessingConfig, preprocess
    from soma.signal.cohort_synthetic import cohort_recording

    raw, _ = cohort_recording(1, 4)
    original = raw.get_data().copy()
    cfg = PreprocessingConfig(
        reference="channels", reference_channels=("Fz", "Pz"), highpass_hz=None, lowpass_hz=None
    )
    result = preprocess(raw, cfg)
    expected = original - original[[3, 4]].mean(axis=0, keepdims=True)
    np.testing.assert_allclose(result.data, expected)
    np.testing.assert_array_equal(raw.get_data(), original)
    assert result.summary["reference_channels"] == ["Fz", "Pz"]
    for bad in (
        replace(cfg, reference_channels=("unavailable",)),
        replace(cfg, reference_channels=("Fz", "Fz")),
        replace(cfg, reference="average"),
    ):
        with pytest.raises(ValueError):
            preprocess(raw, bad)
