import os
from pathlib import Path

import numpy as np
import pytest

from soma.datasets.eegbci import recording_path
from soma.decoding.config import read_protocol
from soma.decoding.data import load_trials
from soma.decoding.evaluation import FitAudit, fit_fold
from soma.decoding.features import build_bank
from soma.decoding.splits import outer_splits

pytestmark = pytest.mark.integration


def test_cached_real_identified_trials_and_train_only_pipelines(tmp_path):
    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not all(recording_path(root, 1, run).is_file() for run in (4, 8, 12)):
        pytest.skip("Explicit cached subject 1 runs required; no downloads")
    protocol, _ = read_protocol(Path("configs/decoding.yaml"))
    data, records = load_trials(root, (1,), protocol, cache=tmp_path / "cache")
    assert len(records) == 3
    assert all(row["status"] == "complete" for row in records)
    assert data.X.shape[1:] == (9, 320)
    assert data.context.shape[1:] == (9, 640)
    assert tuple(data.channels) == tuple(protocol["channels"])
    second, hits = load_trials(root, (1,), protocol, cache=tmp_path / "cache")
    assert all(row["cache_hit"] for row in hits)
    assert data.fingerprint == second.fingerprint
    np.testing.assert_array_equal(data.X, second.X)
    bank = build_bank(data)
    fold = outer_splits(data, "within-subject")[0]
    for model in ("multiband_lr", "csp_lda", "tangent_lr", "burst_lr"):
        audit = FitAudit()
        pipeline, pred, scores, _ = fit_fold(bank, model, protocol, fold, {}, audit, phase="outer")
        assert len(pred) == len(fold.test)
        assert np.isfinite(scores).all()
        assert audit.fits[0]["n_train"] == len(fold.train)


def test_trial_cache_identity_tamper_is_explicit_failure(tmp_path):
    import json

    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not all(recording_path(root, 1, run).is_file() for run in (4, 8, 12)):
        pytest.skip("Explicitly cached EDFs required")
    protocol, _ = read_protocol(Path("configs/decoding.yaml"))
    _, records = load_trials(root, (1,), protocol, cache=tmp_path / "cache")
    receipt = tmp_path / "cache" / records[0]["cache_key"] / "receipt.json"
    values = json.loads(receipt.read_text())
    values["identity"] = "other-experiment"
    receipt.write_text(json.dumps(values))
    _, result = load_trials(root, (1,), protocol, cache=tmp_path / "cache")
    assert result[0]["status"] == "failed"
    assert "identity/schema" in result[0]["error"]
    assert all(row["status"] == "complete" for row in result[1:])
