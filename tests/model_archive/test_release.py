"""Complete release provenance, numeric parity and rejection boundaries."""

import copy

import numpy as np
import pytest

from soma.external_eeg.synthetic import fictional
from soma.model_archive.archive import frozen_prediction, inspect_archive, verify_release
from soma.model_archive.protocol import inspect_training, seal_training
from soma.model_archive.training import archive_models
from soma.workflow.model import digest


@pytest.fixture(scope="module")
def released(tmp_path_factory):
    data = fictional()
    folder = tmp_path_factory.mktemp("archive") / "release"
    sealed = seal_training("a" * 64, True)
    manifest = archive_models(data, sealed, folder)
    return folder / "manifest/result.json", manifest, data


def test_complete_five_models_and_source_validation(released):
    path, d, _ = released
    assert set(d["models"]) == {"dummy", "multiband_lr", "csp_lda", "riemann_mdm", "tangent_lr"}
    actual = inspect_archive(path, d["id"])
    assert actual["historical_m22"] is False
    verified = verify_release(path, d["id"], path.parent.parent / "probe/result.json")
    assert verified["status"] == "VERIFIED"
    assert all(r["labels_exact"] for r in verified["models"].values())


def test_prediction_never_calls_fit_and_is_immutable(released, monkeypatch):
    from sklearn.pipeline import Pipeline

    from soma.decoding.covariance import TrialCovariances
    from soma.external_eeg import models
    from soma.results.io import load_result

    path, d, _ = released

    def forbidden(*args, **kwargs):
        raise AssertionError("Prediction attempted fitting")

    monkeypatch.setattr(Pipeline, "fit", forbidden)
    monkeypatch.setattr(TrialCovariances, "fit", forbidden)
    monkeypatch.setattr(models, "freeze", forbidden)
    _, a = load_result(path.parent.parent / "probe/result.json")
    first = frozen_prediction(
        path, d["id"], "tangent_lr", d["contract"], a["X"], a["powers"], a["covariances"]
    )
    second = frozen_prediction(
        path, d["id"], "tangent_lr", d["contract"], a["X"], a["powers"], a["covariances"]
    )
    for x, y in zip(first, second, strict=True):
        np.testing.assert_array_equal(x, y)
    assert (
        verify_release(path, d["id"], path.parent.parent / "probe/result.json")["status"]
        == "VERIFIED"
    )


@pytest.mark.parametrize(
    "field",
    [
        "classes",
        "contract",
        "source_fingerprint",
        "models",
        "protocol",
        "historical_m22",
        "schema",
        "inventory_fingerprint",
    ],
)
def test_tampered_manifest_is_rejected(released, tmp_path, field):
    from soma.results.contracts import seal
    from soma.results.io import inspect_result, save_result

    path, d, _ = released
    e = copy.deepcopy(inspect_result(path)["envelope"])
    e["payload"]["values"][field] = "tampered"
    save_result(seal(e), {}, tmp_path / "manifest")
    with pytest.raises((ValueError, TypeError, KeyError)):
        inspect_archive(tmp_path / "manifest/result.json", d["id"])


@pytest.mark.parametrize("fault", ["units", "channels", "reference_scope", "fs_hz", "event_origin"])
def test_transfer_contract_changes_rejected(released, fault):
    from soma.results.io import load_result

    path, d, _ = released
    c = copy.deepcopy(d["contract"])
    c[fault] = "wrong"
    _, a = load_result(path.parent.parent / "probe/result.json")
    with pytest.raises(ValueError):
        frozen_prediction(path, d["id"], "multiband_lr", c, a["X"], a["powers"], a["covariances"])


def test_unapproved_training_amendment():
    from soma.protocol.model import SealedProtocol
    from soma.results.contracts import canonical

    sealed = seal_training(digest({"source": "fictional"}), True)
    changed = sealed.record()
    changed["protocol"]["optional_metadata"]["training"]["parameters"]["tangent_lr"] = {
        "classifier__C": 1000
    }
    with pytest.raises(ValueError):
        inspect_training(SealedProtocol(canonical(changed)))


def test_target_subjects_and_wrong_dataset_rejected(tmp_path):
    from dataclasses import replace

    d = fictional()
    changed = replace(d, provenance={**d.provenance, "dataset": "eegmmidb"})
    with pytest.raises(ValueError, match="dataset"):
        archive_models(changed, seal_training("a" * 64, True), tmp_path / "bad")
    frame = d.metadata.copy()
    frame["subject"] = 99
    changed = replace(d, metadata=frame)
    with pytest.raises(ValueError, match="leakage"):
        archive_models(changed, seal_training("a" * 64, True), tmp_path / "bad")


@pytest.mark.parametrize(
    "fault", ["class_order", "no_input_fingerprint", "unsupported_schema", "inventory_protocol"]
)
def test_resealed_but_scientifically_invalid_release_rejected(released, tmp_path, fault):
    import shutil

    from soma.model_archive.archive import numerical_receipt

    path, original, _ = released
    root = tmp_path / "copy"
    shutil.copytree(path.parent.parent, root)
    shutil.rmtree(root / "manifest")
    d = copy.deepcopy(original)
    if fault == "class_order":
        d["classes"] = [1, 0]
    elif fault == "no_input_fingerprint":
        d["source_fingerprint"] = ""
    elif fault == "unsupported_schema":
        d["schema"] = "soma.model-release/999"
    else:
        d["inventory_fingerprint"] = "b" * 64
    d.pop("id")
    d["id"] = digest(d)
    numerical_receipt(d, {}, root / "manifest", "soma.model-release")
    with pytest.raises(ValueError):
        inspect_archive(root / "manifest/result.json", d["id"])


@pytest.mark.parametrize("fault", ["corrupt_array", "missing_component", "float32_component"])
def test_numeric_capsule_damage_is_rejected(released, tmp_path, fault):
    import shutil

    from soma.external_eeg.models import import_model

    path, d, _ = released
    original = path.parent.parent / "models/multiband_lr"
    copied = tmp_path / "model"
    shutil.copytree(original, copied)
    array = next((copied / "arrays").glob("*.npy"))
    if fault == "missing_component":
        array.unlink()
    elif fault == "corrupt_array":
        content = bytearray(array.read_bytes())
        content[-1] ^= 1
        array.write_bytes(content)
    else:
        np.save(array, np.load(array, allow_pickle=False).astype(np.float32), allow_pickle=False)
    with pytest.raises(ValueError):
        import_model(copied / "result.json", d["models"]["multiband_lr"]["id"])


def test_unsupported_environment_is_not_silently_portable(released, monkeypatch):
    from soma.external_eeg import models

    path, d, _ = released
    monkeypatch.setattr(models, "environment_snapshot", lambda: {"unverified": "different-build"})
    with pytest.raises(ValueError, match="environment"):
        verify_release(path, d["id"], path.parent.parent / "probe/result.json")


def test_model_protocol_binding_cannot_be_reused_for_other_input(released, tmp_path):
    from soma.model_archive.archive import verify_release

    path, d, _ = released
    bad = tmp_path / "probe.json"
    bad.write_bytes(b"{}")
    with pytest.raises(ValueError, match="probe identity"):
        verify_release(path, d["id"], bad)


def test_restricted_model_arrays_cannot_enter_explorer_summary(released, tmp_path):
    from services.explorer_api.model_archive import demo, read_summary
    from soma.model_archive.archive import numerical_receipt

    d = demo()
    d["source_validation"] = {"coef": [1, 2]}
    numerical_receipt(d, {}, tmp_path / "bad", "soma.model-release-summary")
    with pytest.raises(ValueError, match="Private"):
        read_summary(tmp_path / "bad/result.json")


def test_human_fitting_requires_permission_before_feature_computation(tmp_path):
    from dataclasses import replace

    d = fictional()
    frame = d.metadata.copy()
    frame["run"] = frame.run.map({1: 4, 2: 8, 3: 12, 4: 4, 5: 8, 6: 12})
    human = replace(d, metadata=frame, provenance={**d.provenance, "dataset": "eegmmidb"})
    with pytest.raises(ValueError, match="permission"):
        archive_models(human, seal_training("a" * 64), tmp_path / "denied")
    assert not (tmp_path / "denied").exists()


def test_sdk_and_cli_expose_actual_archive_operations(tmp_path):
    from typer.testing import CliRunner

    from soma.cli import app
    from soma.sdk import eeg_benchmark as sdk

    assert sdk.archive_fitted_models is archive_models
    runner = CliRunner()
    result = runner.invoke(
        app, ["benchmark", "external", "acquisition-plan", str(tmp_path / "plan.json")]
    )
    assert result.exit_code == 0, result.output
    assert "EXTERNAL_DATA_ACQUISITION_BLOCKED" in result.output
    assert runner.invoke(app, ["model", "--help"]).exit_code == 0


@pytest.mark.parametrize("fault", ["float32", "missing_scale", "wrong_protocol"])
def test_self_consistent_capsule_still_requires_complete_release_contract(
    released, tmp_path, fault
):
    import shutil

    from soma.core.provenance import sha256
    from soma.model_archive.archive import numerical_receipt
    from soma.results.io import load_result
    from soma.sdk.provenance import array_fingerprint

    path, d, _ = released
    root = tmp_path / "release"
    shutil.copytree(path.parent.parent, root)
    capsule = root / "models/multiband_lr/result.json"
    e, a = load_result(capsule)
    state = dict(e["payload"]["values"])
    if fault == "float32":
        a["coef"] = a["coef"].astype(np.float32)
    elif fault == "missing_scale":
        a.pop("scale")
    else:
        state["training"]["protocol_fingerprint"] = "b" * 64
    state.pop("id")
    state["id"] = digest(
        {"metadata": state, "arrays": {k: array_fingerprint(v) for k, v in a.items()}}
    )
    shutil.rmtree(capsule.parent)
    numerical_receipt(state, a, capsule.parent, "soma.external-eeg.model")
    changed = copy.deepcopy(d)
    changed["models"]["multiband_lr"].update(id=state["id"], sha256=sha256(capsule))
    changed.pop("id")
    changed["id"] = digest(changed)
    shutil.rmtree(root / "manifest")
    numerical_receipt(changed, {}, root / "manifest", "soma.model-release")
    with pytest.raises(ValueError):
        inspect_archive(root / "manifest/result.json", changed["id"])


def test_read_only_api_cannot_load_private_weight_manifest(tmp_path):
    from fastapi.testclient import TestClient

    from services.explorer_api.app import create_app

    with TestClient(create_app(jobs_root=tmp_path / "jobs"), base_url="http://127.0.0.1") as client:
        r = client.get("/api/model-archives/demo-model-archive")
        assert r.status_code == 200 and r.json()["human_external_accuracy"] is None
        assert client.post("/api/model-archives/demo-model-archive").status_code == 405
        assert client.get("/api/model-archives/unconfigured").status_code == 404
