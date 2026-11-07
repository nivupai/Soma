import copy
import json

import mne
import numpy as np
import pytest
from numpy.testing import assert_allclose
from typer.testing import CliRunner

from soma.anatomy.contracts import validate_eeg_info
from soma.anatomy.synthetic import synthetic_info
from soma.anatomy.task_power import short_epoch_band_power
from soma.cli import app
from soma.datasets.matched import SampleAssets
from soma.datasets.openneuro import selected_inventory


@pytest.mark.parametrize(
    "command", ["inspect", "coregister", "validate-bem", "watershed", "fetch-selected"]
)
def test_anatomy_cli_help(command):
    result = CliRunner().invoke(app, ["anatomy", command, "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("command", ["build-individual", "uncertainty"])
def test_individual_source_cli_help(command):
    result = CliRunner().invoke(app, ["source", command, "--help"])
    assert result.exit_code == 0


def test_synthetic_cli_help_and_no_implicit_fetch(tmp_path, monkeypatch):
    result = CliRunner().invoke(app, ["anatomy", "experiment", "synthetic", "--help"])
    assert result.exit_code == 0

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network request")

    monkeypatch.setattr(mne.datasets.sample, "data_path", forbidden)
    with pytest.raises(FileNotFoundError):
        SampleAssets(tmp_path).inspect()
    with pytest.raises(ValueError):
        SampleAssets(tmp_path, subject="fsaverage").inspect()
    with pytest.raises(ValueError):
        SampleAssets(tmp_path, subject="morph").fetch()


@pytest.mark.parametrize(
    "failure", ["no_average", "duplicate", "wrong_unit", "wrong_frame", "bad_channel"]
)
def test_eeg_info_rejects_invalid_sensor_states(failure):
    info = synthetic_info()
    if failure == "no_average":
        raw = mne.io.RawArray(np.zeros((24, 2)), info, verbose=False)
        raw.del_proj()
        info = raw.info
    elif failure == "duplicate":
        info["chs"][0]["loc"][:3] = info["chs"][1]["loc"][:3]
    elif failure == "wrong_unit":
        info["chs"][0]["unit"] = 112
    elif failure == "wrong_frame":
        info["chs"][0]["coord_frame"] = 5
    else:
        info["bads"] = [info.ch_names[0]]
    with pytest.raises(ValueError):
        validate_eeg_info(info)


def test_short_epoch_power_does_not_require_evoked_only():
    t = np.arange(112) / 160
    x = np.sin(2 * np.pi * 10 * t)
    trials = np.array([x, -x])
    individual = short_epoch_band_power(trials, 160)
    evoked = short_epoch_band_power(trials.mean(axis=0, keepdims=True), 160)
    assert np.all(individual > 0.4)
    assert evoked[0] == 0


def test_selected_subject_inventory_cannot_mix_subjects():
    metadata = {
        "subjects": ["sub-01", "sub-02"],
        "files": ["sub-01/anat/T1.nii", "sub-02/meg/a.fif"],
        "license": "CC0",
        "repository_tree_sha": "fixture",
    }
    result = selected_inventory(metadata, "sub-01")
    assert result["files"] == ["sub-01/anat/T1.nii"]
    assert not result["automatic_download"]
    with pytest.raises(ValueError):
        selected_inventory(metadata, "sub-99")


@pytest.mark.integration
def test_actual_matched_EEG_BEM_and_correspondence(tmp_path):
    from soma.source.individual import individual_forward, prepare_sample, require_correspondence

    if not SampleAssets().raw_path.exists():
        pytest.skip("Explicit sample cache required; never fetch")
    assets, model, src, prepared = prepare_sample()
    json.dumps(prepared, allow_nan=False)
    assert prepared["identity"]["MRI_geometry"]["shape"] == [256, 256, 256]
    assert prepared["identity"]["EEG_retained"] == 59
    assert prepared["identity"]["EEG_digitization_correspondence_max_m"] == 0
    assert prepared["readiness"]["status"] == "INDETERMINATE"
    assert prepared["readiness"]["computational_readiness"] == "PASS"
    fwd, receipt = individual_forward(model, src)
    assert fwd.matrix.shape == (59, 1239)
    assert fwd.diagnostics()["rank"] == 58
    bem = mne.read_bem_solution(receipt["BEM"]["path"], verbose=False)
    assert [int(s["id"]) for s in bem["surfs"]] == [4, 3, 1]
    assert_allclose([s["sigma"] for s in bem["surfs"]], [0.3, 0.006, 0.3])
    fresh = mne.make_forward_solution(
        model.info,
        trans=model.head_to_mri.to_mne(),
        src=src,
        bem=bem,
        meg=False,
        eeg=True,
        mindist=5,
        n_jobs=1,
        verbose=False,
    )
    fixed = mne.convert_forward_solution(
        fresh, surf_ori=True, force_fixed=True, use_cps=False, copy=True, verbose=False
    )
    assert_allclose(fwd.matrix, fwd.projector @ fixed["sol"]["data"], atol=2e-5, rtol=5e-5)
    clone = copy.copy(fwd)
    clone.anatomy = {**fwd.anatomy, "subject": "wrong"}
    with pytest.raises(ValueError):
        require_correspondence(fwd, clone)
    clone = copy.copy(fwd)
    clone.vertices = [x[::-1] for x in fwd.vertices]
    with pytest.raises(ValueError):
        require_correspondence(fwd, clone)
    clone = copy.copy(fwd)
    clone.info = mne.pick_info(fwd.info, np.arange(59)[::-1])
    with pytest.raises(ValueError):
        require_correspondence(fwd, clone)
    with pytest.raises(ValueError):
        individual_forward(model, src, conductivities=(0.3, -0.01, 0.3))


def test_meg_acquired_transform_preserved_without_weakening_rigid_contract():
    from soma.geometry import Frame, Transform
    from soma.source.meg_matched import measured_device_transform

    matrix = np.eye(4)
    matrix[0, 0] += 3e-7
    info = {"dev_head_t": {"from": 1, "to": 4, "trans": matrix}}
    transform, receipt = measured_device_transform(info)
    assert_allclose(transform.matrix, matrix, atol=0, rtol=0)
    assert not receipt["matrix_modified"]
    with pytest.raises(ValueError):
        Transform(Frame.DEVICE, Frame.HEAD, matrix)
    matrix[0, 0] = 1.001
    with pytest.raises(ValueError):
        measured_device_transform(info)
    info["dev_head_t"]["to"] = 5
    with pytest.raises(ValueError):
        measured_device_transform(info)
