import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from soma.decoding import workflows
from soma.decoding.config import digest, identity, read_protocol
from soma.decoding.models import parameter_grid
from soma.decoding.synthetic import simulate_decoding


def frozen_fixture(tmp_path):
    protocol, checksum = read_protocol(Path("configs/decoding.yaml"))
    dataset, _ = simulate_decoding(n_subjects=3, n_trials=6)
    values = dict(
        protocol=protocol,
        initial_protocol_sha256=checksum,
        selected_parameters={
            model: parameter_grid(model, protocol, True)[0] for model in protocol["models"]
        },
        software=identity(),
        verification_sha256="fixture",
        development_dataset_fingerprint=dataset.fingerprint,
        frozen_at_utc="2026-11-07T00:00:00+00:00",
        heldout_accessed=False,
    )
    path = tmp_path / "frozen.yaml"
    return path, values, dataset


def write_frozen(path, values):
    path.write_text(yaml.safe_dump(values))
    path.with_suffix(".sha256").write_text(digest(values) + "\n")


def test_protocol_seal_tampering_and_initial_receipt(tmp_path):
    values, checksum = read_protocol(Path("configs/decoding.yaml"))
    assert checksum == "11912588d1457a334580eab3fa1093367a762ee94c0157ed6d71cdaa849547bf"
    path = tmp_path / "test.yaml"
    write_frozen(path, values)
    values["fixed"]["logistic_C"] = 999
    path.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="seal"):
        read_protocol(path)


def test_frozen_choices_must_stay_inside_search_space(tmp_path):
    path, values, _ = frozen_fixture(tmp_path)
    values["selected_parameters"]["tangent_lr"] = {"classifier__C": 999}
    write_frozen(path, values)
    with pytest.raises(ValueError, match="outside"):
        read_protocol(path)
    values["initial_protocol_sha256"] = "different"
    write_frozen(path, values)
    with pytest.raises(ValueError, match="retain"):
        read_protocol(path)


def test_freeze_rejects_incomplete_development_before_loading_data(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Data must not be read")

    monkeypatch.setattr(workflows, "load_trials", forbidden)
    with pytest.raises(ValueError, match="finish first"):
        workflows.freeze_heldout(
            tmp_path,
            Path("configs/decoding.yaml"),
            tmp_path / "missing",
            tmp_path / "out.yaml",
            tmp_path / "verification.json",
        )


def test_stale_code_rejected_before_heldout_fetch_or_load(tmp_path, monkeypatch):
    path, values, _ = frozen_fixture(tmp_path)
    values["software"] = {"stale": True}
    write_frozen(path, values)

    def forbidden(*args, **kwargs):
        raise AssertionError("Held-out fetch/read must not occur")

    monkeypatch.setattr(workflows, "load_trials", forbidden)
    monkeypatch.setattr(workflows, "fetch", forbidden)
    with pytest.raises(ValueError, match="matching frozen"):
        workflows.evaluate_heldout(
            tmp_path, path, tuple(range(36, 66)), tmp_path / "evaluation", fetch_data=True
        )
    assert not (tmp_path / "evaluation").exists()


def test_secondary_heldout_failure_cannot_be_reported_as_complete(tmp_path, monkeypatch):
    path, values, data = frozen_fixture(tmp_path)
    write_frozen(path, values)
    metadata = data.metadata.copy()
    metadata["subject"] += 35
    metadata["trial_id"] = "target-" + metadata.trial_id
    metadata["recording"] = "target-" + metadata.recording
    target = replace(data, metadata=metadata)
    monkeypatch.setattr(
        workflows,
        "load_trials",
        lambda *args, **kwargs: (target if kwargs.get("heldout") else data, []),
    )
    monkeypatch.setattr(workflows, "build_bank", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflows, "evaluate", lambda *args, **kwargs: {"status": "complete"})
    monkeypatch.setattr(workflows, "adaptation", lambda *args, **kwargs: {"status": "failed"})
    output = tmp_path / "evaluation"
    result = workflows.evaluate_heldout(tmp_path, path, tuple(range(36, 66)), output, plots=False)
    assert result["status"] == "partial"
    assert result["mode_statuses"]["adaptation"] == "failed"
    receipt = json.loads((output / "heldout_receipt.json").read_text())
    assert receipt["mode_statuses"]["adaptation"] == "failed"
    assert (output / "access_started.json").is_file()


def test_null_replication_count_must_be_positive(tmp_path):
    protocol, _ = read_protocol(Path("configs/decoding.yaml"))
    with pytest.raises(ValueError, match="positive"):
        workflows.run_nulls(None, protocol, tmp_path / "null", repetitions=0)
