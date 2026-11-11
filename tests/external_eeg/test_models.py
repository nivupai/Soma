"""Independent unchanged-pipeline parity, state corruption and leakage tests."""

import copy

import numpy as np
import pytest

from soma.decoding.models import make_pipeline
from soma.eeg_benchmark.evaluation import bank
from soma.eeg_benchmark.protocol import MODELS
from soma.external_eeg.contracts import feature_contract, parameters, plan
from soma.external_eeg.models import freeze, import_model, predict
from soma.external_eeg.study import split_indices
from soma.external_eeg.synthetic import fictional


@pytest.fixture(scope="module")
def fixture():
    d = fictional()
    p = plan()
    f = bank(d, parameters())
    tr, te = split_indices(d, p)
    return d, p, f, tr, te


@pytest.mark.parametrize("model", MODELS)
def test_numeric_capsule_matches_unchanged_soma_pipeline(fixture, tmp_path, model):
    d, p, f, tr, te = fixture
    pipeline = None
    prior = float(d.y[tr].mean())
    if model != "dummy":
        pipeline = make_pipeline(
            model, parameters(), p["parameters"][model], precomputed_covariance=True
        )
        pipeline.fit(f.input(model)[tr], d.y[tr])
    identity = freeze(
        pipeline,
        model,
        feature_contract("synthetic-nine"),
        {"origin": "SYNTHETIC_SOURCE_FIT"},
        tmp_path / "model",
        prior=prior,
    )
    pred, score, prob = predict(
        tmp_path / "model/result.json",
        identity,
        feature_contract("synthetic-nine"),
        d.X[te],
        f.logpowers[te],
        f.covariances[te],
    )
    if model == "dummy":
        np.testing.assert_array_equal(pred, np.full(len(te), int(prior > 0.5)))
    else:
        np.testing.assert_array_equal(pred, pipeline.predict(f.input(model)[te]))
        np.testing.assert_allclose(
            score, pipeline.decision_function(f.input(model)[te]), rtol=1e-9, atol=1e-9
        )
        if prob is not None:
            np.testing.assert_allclose(
                prob, pipeline.predict_proba(f.input(model)[te])[:, 1], atol=1e-10
            )
    with pytest.raises(ValueError, match="identity"):
        import_model(tmp_path / "model/result.json", "a" * 64)
    array = next((tmp_path / "model/arrays").glob("*.npy"))
    array.write_bytes(b"corruption")
    with pytest.raises(ValueError):
        import_model(tmp_path / "model/result.json", identity)


@pytest.mark.parametrize(
    "fault", ["units", "channels", "sampling", "labels", "reference", "epoch", "order"]
)
def test_feature_contract_rejects_incompatible_changes(fault):
    from soma.external_eeg.contracts import compatibility

    c = feature_contract()
    other = copy.deepcopy(c)
    if fault == "units":
        other["units"] = "uV"
    elif fault == "channels":
        other["channels"].pop()
    elif fault == "sampling":
        other["fs_hz"] = 250
    elif fault == "labels":
        other["labels"] = {"left_hand": 1, "right_hand": 0}
    elif fault == "reference":
        other["reference_scope"] = "left-mastoid"
    elif fault == "epoch":
        other["epoch_s"] = [0.0, 2.0]
    else:
        other["channels"].reverse()
    with pytest.raises(ValueError):
        compatibility(c, other)


def test_reference_change_is_not_exact_transfer():
    from soma.external_eeg.contracts import compatibility

    assert (
        compatibility(feature_contract("eegbci-average-all-eeg"), feature_contract())["status"]
        == "NOT_COMPARABLE"
    )


def test_target_data_does_not_change_source_fitted_state(fixture, tmp_path):
    d, p, f, tr, te = fixture
    for model in MODELS[1:]:
        a = make_pipeline(model, parameters(), p["parameters"][model], precomputed_covariance=True)
        b = make_pipeline(model, parameters(), p["parameters"][model], precomputed_covariance=True)
        original = f.input(model).copy()
        changed = original.copy()
        changed[te] *= 100
        a.fit(original[tr], d.y[tr])
        b.fit(changed[tr], d.y[tr])
        x = freeze(
            a,
            model,
            feature_contract("synthetic-nine"),
            {"origin": "SYNTHETIC_SOURCE_FIT"},
            tmp_path / (model + "a"),
        )
        y = freeze(
            b,
            model,
            feature_contract("synthetic-nine"),
            {"origin": "SYNTHETIC_SOURCE_FIT"},
            tmp_path / (model + "b"),
        )
        assert x == y


def test_model_cannot_claim_original_m22(tmp_path):
    with pytest.raises(ValueError, match="original M22"):
        freeze(
            None, "dummy", feature_contract(), {"origin": "M22_ORIGINAL"}, tmp_path / "x", prior=0.5
        )
