import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from soma.cli import _subject_selection, app
from soma.eeg.reference_audit import covariance_identity, spectral_identity
from soma.experiments.config import CohortConfig
from soma.experiments.replication import eligible_effects, load_protocol, protocol_digest
from soma.signal.spectral import WelchConfig
from soma.simulations.calibration import CalibrationConfig, calibrate
from soma.statistics.robustness import current_generation, influence_tables


def test_reference_algebra_known_common_mode():
    time = np.arange(1600) / 160
    local = 2 * np.sin(2 * np.pi * 10 * time)
    common = 3 * np.cos(2 * np.pi * 20 * time)
    row = covariance_identity(local + common, common)
    assert row["actual_referenced_variance_v2"] == pytest.approx(2)
    assert row["acquisition_variance_v2"] == pytest.approx(6.5)
    assert abs(row["identity_error_v2"]) < 1e-12
    for row in spectral_identity(local + common, common, 160, WelchConfig()):
        assert abs(row["identity_error_v2"]) < 1e-12
    scaled = covariance_identity((local + common) * 1e-6, common * 1e-6)
    assert scaled["actual_referenced_variance_v2"] == pytest.approx(2e-12, abs=1e-25)


@pytest.mark.parametrize(
    "x,r",
    [(np.ones(3), np.ones(2)), (np.array([]), np.array([])), (np.array([np.nan]), np.ones(1))],
)
def test_reference_rejects_invalid(x, r):
    with pytest.raises(ValueError):
        covariance_identity(x, r)


def effect_tables():
    rows = [
        {
            "subject": s,
            "run": r,
            "channel": "C3",
            "band": "mu",
            "outcome": "log_absolute_power",
            "units": "log(V²)",
            "contrast": float(s),
        }
        for s in (1, 2, 3)
        for r in (4, 8)
    ]
    runs = pd.DataFrame(rows)
    subjects = (
        runs.groupby(["subject", "channel", "band", "outcome", "units"])
        .agg(contrast=("contrast", "mean"))
        .reset_index()
    )
    return subjects, runs


def test_independent_subject_influence_and_run_eligibility():
    subjects, runs = effect_tables()
    tables = influence_tables(subjects, runs, minimum_paired_runs=2)
    loo = tables["leave_one_subject_out"].set_index("excluded_subject")
    assert loo.loc[1, "estimate"] == 2.5
    assert loo.loc[3, "estimate"] == 1.5
    assert loo.loc[2, "change"] == 0
    run = tables["leave_one_run_out"]
    assert not run.subject_still_eligible.any()
    assert (run.n_subjects == 2).all()


def test_generation_pointer_cannot_escape(tmp_path):
    (tmp_path / "current.json").write_text(json.dumps({"generation": "../outside"}))
    with pytest.raises(ValueError):
        current_generation(tmp_path)


def test_frozen_protocol_receipt_and_tampering(tmp_path):
    path = Path("configs/replication.yaml")
    protocol, digest = load_protocol(path)
    assert digest == "9995060c58ffb3a896d725ef9641f27fb7645950b76fbbf59b6ee97f3488ab61"
    assert protocol["primary"]["interval"] == "t"
    other = tmp_path / "test.json"
    other.write_text(json.dumps(protocol))
    other.with_suffix(".sha256").write_text(digest)
    assert load_protocol(other)[1] == digest
    protocol["primary"]["interval"] = "bca"
    other.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="seal"):
        load_protocol(other)
    assert protocol_digest(protocol) != digest


def test_expansion_requires_explicit_flag():
    assert _subject_selection("6:35") == tuple(range(6, 36))
    with pytest.raises(ValueError, match="expand-all"):
        _subject_selection("all")
    assert len(_subject_selection("all", True)) == 109
    for value in ("2:1", "1,1", "110", "0"):
        with pytest.raises(ValueError):
            _subject_selection(value)


@pytest.mark.parametrize(
    "command",
    [
        ["eeg", "replicate"],
        ["eeg", "audit-reference"],
        ["stats", "calibrate"],
        ["stats", "influence"],
    ],
)
def test_cli_help(command):
    assert CliRunner().invoke(app, [*command, "--help"]).exit_code == 0


def test_calibration_schedule_resume_and_corruption(tmp_path):
    cfg = CalibrationConfig(
        scenarios=("normal",),
        subject_counts=(5,),
        methods=("percentile", "t"),
        repetitions=20,
        n_resamples=199,
        chunk_size=5,
    )
    serial, parallel = tmp_path / "serial", tmp_path / "parallel"
    calibrate(serial, cfg, workers=1, plots=False)
    calibrate(parallel, cfg, workers=2, plots=False)
    for path in (serial / "chunks").glob("*.csv"):
        assert path.read_bytes() == (parallel / "chunks" / path.name).read_bytes()
    result = calibrate(serial, cfg, resume=True, plots=False)
    assert result["status"] == "complete"
    assert len(list((serial / "chunks").glob("*.csv"))) == 4
    with pytest.raises(ValueError, match="mismatch"):
        calibrate(serial, replace(cfg, seed=1), resume=True, plots=False)
    first = next((serial / "chunks").glob("*.csv"))
    first.write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        calibrate(serial, cfg, resume=True, plots=False)


def test_missing_runs_and_trial_minimum():
    rows = []
    for subject in (1, 2):
        for run in (4, 8) if subject == 1 else (4,):
            for condition, power in [("left hand imagery", np.e), ("right hand imagery", 1.0)]:
                rows.append(
                    dict(
                        subject=subject,
                        run=run,
                        channel="C3",
                        band="mu",
                        kind="imagery",
                        condition=condition,
                        absolute_power_v2=power,
                        erd_percent=0.0,
                        log_power_ratio=0.0,
                    )
                )
    features = pd.DataFrame(rows)
    cfg = CohortConfig(subjects=(1, 2), runs=(4, 8))
    _, subjects = eligible_effects(features, cfg, 2)
    selected = subjects[
        (subjects.channel == "C3")
        & (subjects.band == "mu")
        & (subjects.outcome == "log_absolute_power")
    ].set_index("subject")
    assert selected.loc[1, "contrast"] == pytest.approx(1)
    assert np.isnan(selected.loc[2, "contrast"])
    assert selected.loc[2, "exclusion_reason"] == "insufficient_paired_runs"
    _, stricter = eligible_effects(features, cfg, 2, minimum_trials=2)
    assert not stricter.included.any()


def test_robustness_flags_channel_missingness_and_reference_sign():
    from soma.experiments.replication import robustness_flags

    protocol, _ = load_protocol(Path("configs/replication.yaml"))
    population = pd.DataFrame(
        [
            dict(
                channel=channel,
                band="mu",
                outcome="log_absolute_power",
                method="t",
                estimate=estimate,
                n_subjects=30,
                n_requested=30,
                status="ok",
            )
            for channel, estimate in [("C3", 0.1), ("C4", -0.2)]
        ]
    )
    influence = pd.DataFrame(
        [
            dict(channel=c, band="mu", outcome="log_absolute_power", sign_agrees=True)
            for c in ["C3", "C4"]
        ]
    )
    coverage = dict(
        subject_fraction=1.0,
        record_fraction=1.0,
        trial_retention=0.9,
        missing_reference_fraction=0.0,
        missing_reference_C3_mu=0.2,
    )
    configs = pd.concat(
        [
            population.assign(variant="primary"),
            population.assign(variant="reference_none", estimate=-0.1),
        ]
    )
    flags = robustness_flags(population, influence, protocol, coverage, configs).set_index(
        "channel"
    )
    assert "reference_dependent_sign" in flags.loc["C3", "flags"]
    assert "insufficient_reference_data" in flags.loc["C3", "flags"]
    assert "reference_dependent_sign" not in flags.loc["C4", "flags"]
    assert "insufficient_reference_data" not in flags.loc["C4", "flags"]


def test_small_effect_coverage_uses_per_channel_effective_n():
    from soma.experiments.replication import robustness_flags

    protocol, _ = load_protocol(Path("configs/replication.yaml"))
    population = pd.DataFrame(
        [
            dict(
                channel=c,
                band="mu",
                outcome="log_absolute_power",
                method="t",
                estimate=0.1,
                n_subjects=n,
                n_requested=30,
                status="ok",
            )
            for c, n in [("C3", 30), ("C4", 10)]
        ]
    )
    influence = pd.DataFrame(
        [
            dict(channel=c, band="mu", outcome="log_absolute_power", sign_agrees=True)
            for c in ["C3", "C4"]
        ]
    )
    coverage = dict(
        subject_fraction=1.0,
        record_fraction=1.0,
        trial_retention=0.9,
        missing_reference_fraction=0.0,
    )
    flags = robustness_flags(population, influence, protocol, coverage).set_index("channel")
    assert "subject_fraction_below_declared_threshold" in flags.loc["C4", "flags"]
    assert "subject_fraction_below_declared_threshold" not in flags.loc["C3", "flags"]


def test_reference_audit_rejects_nonimagery_selection(tmp_path):
    from soma.eeg.reference_audit import audit_reference

    with pytest.raises(ValueError, match="unilateral"):
        audit_reference(tmp_path, tmp_path / "audit", (1,), (1,), plots=False)


def test_holm_preserves_two_planned_tests_when_one_channel_unavailable():
    from soma.experiments.replication import _infer_table

    protocol, _ = load_protocol(Path("configs/replication.yaml"))
    protocol["inference"]["n_resamples"] = 199
    subjects = pd.DataFrame(
        [
            dict(
                subject=s,
                channel=c,
                band="mu",
                outcome="log_absolute_power",
                units="natural_log_ratio",
                contrast=float(s) if c == "C3" else np.nan,
            )
            for s in range(1, 6)
            for c in ("C3", "C4")
        ]
    )
    table = _infer_table(subjects, protocol)
    result = table[(table.channel == "C3") & (table.method == "t")].iloc[0]
    # Five positive independent effects: 2 of 32 exact sign patterns are as extreme.
    assert result.p_sign_flip == pytest.approx(2 / 32)
    assert result.p_holm_primary == pytest.approx(4 / 32)
    assert table[table.channel == "C4"].p_holm_primary.isna().all()
