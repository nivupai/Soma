"""Full synthetic execution, resumption, native verification and aggregate publication."""

import json

from soma.eeg_benchmark.protocol import benchmark_protocol, design
from soma.eeg_benchmark.report import aggregate_export, verify_execution
from soma.eeg_benchmark.runner import run_benchmark
from soma.human.permissions import evidence
from soma.workflow.model import digest


def test_all_variants_publish_and_resume(synthetic, tmp_path, monkeypatch):
    from soma.eeg_benchmark import runner

    d, _, _ = synthetic
    records = [{"subject": s, "run": r} for s in range(1, 7) for r in (4, 8, 12)]
    inv = {
        "records": records,
        "fingerprint": digest(records),
        "source_subjects": [1, 2, 3, 4],
        "target_subjects": [5, 6],
    }
    monkeypatch.setattr(runner, "inventory", lambda *a: inv)
    coverage = [{**r, "status": "ELIGIBLE", "n_proposed": 6} for r in records]
    monkeypatch.setattr(runner, "load_dataset", lambda *a, **kw: (d, coverage))
    notice = tmp_path / "notice.txt"
    notice.write_text("EEG Motor Movement/Imagery Open Data Commons Attribution License v1.0")
    permission = evidence(
        "eegmmidb",
        "1.0.0",
        notice.read_bytes(),
        source="https://physionet.org/content/eegmmidb/1.0.0/",
        license="ODC-By-1.0",
        supported=True,
    )
    sealed = benchmark_protocol(design(4, 2), inv["fingerprint"])
    root = tmp_path / "raw"
    root.mkdir()
    out = tmp_path / "output"
    result = run_benchmark(
        sealed, inv, root, permission, notice, b"x" * 32, out, tmp_path / "cache"
    )
    assert result["status"] == "COMPLETE"
    assert len(result["variants"]) == 11
    assert verify_execution(out)["status"] == "VERIFIED"
    aggregate = aggregate_export(out, permission, notice.read_bytes())
    assert not aggregate["participant_rows_exported"]
    assert "subject-" not in json.dumps(aggregate)
    resumed = run_benchmark(
        sealed, inv, root, permission, notice, b"x" * 32, out, tmp_path / "cache"
    )
    assert result == resumed
    file = out / "primary/predictions.local.csv"
    file.write_text(file.read_text() + "corruption")
    import pytest

    with pytest.raises(ValueError, match="Corrupted"):
        verify_execution(out)
