import json
from pathlib import Path

import pandas as pd
import pytest

import soma.experiments.replication as engine
from soma.experiments.replication import load_protocol, protocol_digest, replicate


def sealed_fixture(tmp_path):
    protocol, _ = load_protocol(Path("configs/replication.yaml"))
    protocol["cohort"].update(subjects=[1, 2], runs=[4, 8], synthetic_seed=27)
    protocol["cohort"]["motor"]["preprocessing"]["reference"] = "none"
    protocol["inference"].update(n_resamples=199, sign_flip=False)
    protocol["eligibility"]["minimum_paired_runs"] = 2
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(protocol))
    path.with_suffix(".sha256").write_text(protocol_digest(protocol))
    return path


def test_interrupted_resume_preserves_completed_record(tmp_path, monkeypatch):
    protocol = sealed_fixture(tmp_path)
    output, cache = tmp_path / "replication", tmp_path / "cache"
    original = engine.cached_record
    calls = 0

    def interrupt(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("simulated interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "cached_record", interrupt)
    with pytest.raises(KeyboardInterrupt):
        replicate(tmp_path, output, protocol, cache_root=cache, plots=False, initial=None)
    assert (output / "records/S001R04/checkpoint.json").is_file()
    monkeypatch.setattr(engine, "cached_record", original)
    result = replicate(
        tmp_path, output, protocol, cache_root=cache, plots=False, initial=None, resume=True
    )
    assert result["complete"] == 4
    assert result["resumed"] == 1
    result = replicate(
        tmp_path, output, protocol, cache_root=cache, plots=False, initial=None, resume=True
    )
    assert result["resumed"] == 4
    effects = pd.read_csv(Path(result["generation"]) / "subject_contrasts.csv")
    assert not effects.duplicated(["subject", "channel", "band", "outcome"]).any()
    checkpoint = output / "records/S001R04/features.csv"
    checkpoint.write_text("corrupted")
    # A corrupted record is retained as a failed attempt, never silently consumed.
    result = replicate(
        tmp_path, output, protocol, cache_root=cache, plots=False, initial=None, resume=True
    )
    assert result["failed"] == 1
    assert result["complete"] == 3


def test_all_missing_replication_retains_explicit_failures(tmp_path):
    result = replicate(
        tmp_path / "empty",
        tmp_path / "missing",
        Path("configs/replication.yaml"),
        subjects=(6,),
        runs=(4,),
        plots=False,
        initial=None,
        cache_root=tmp_path / "cache",
    )
    assert result["status"] == "failed"
    assert result["complete"] == 0
    assert result["failed"] == 1
    folder = Path(result["generation"])
    population = pd.read_csv(folder / "population.csv")
    assert population.n_subjects.eq(0).all()
    assert population.status.eq("insufficient_subjects").all()
    assert (folder / "subject_exclusions.csv").is_file()
