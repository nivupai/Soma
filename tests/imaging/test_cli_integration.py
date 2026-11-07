from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.datasets.structural import cached_structural
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.phantoms import asymmetric, known_transform, transformed_asymmetric
from soma.imaging.registration import RegistrationConfig, register, sitk_transform_to_ras
from soma.imaging.validation import transform_error


@pytest.mark.parametrize(
    "command", ["inspect", "validate", "resample", "register", "surfaces", "benchmark"]
)
def test_mri_cli_help(command):
    result = CliRunner().invoke(app, ["mri", command, "--help"])
    assert result.exit_code == 0
    assert "--help" in result.output


@pytest.mark.parametrize("command", ["synthetic", "real"])
def test_mri_experiment_help(command):
    result = CliRunner().invoke(app, ["mri", "experiment", command, "--help"])
    assert result.exit_code == 0
    assert "--output" in result.output


def test_cached_anatomy_missing_never_downloads(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network download")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    with pytest.raises(FileNotFoundError, match="--fetch"):
        cached_structural(tmp_path)


def test_mri_cli_inspect_validate_and_resample(tmp_path):
    path = tmp_path / "phantom.nii"
    save_nifti(asymmetric(), path)
    for command in ("inspect", "validate"):
        result = CliRunner().invoke(app, ["mri", command, "--input", str(path)])
        assert result.exit_code == 0, result.output
    output = tmp_path / "resample"
    result = CliRunner().invoke(
        app,
        [
            "mri",
            "resample",
            "--input",
            str(path),
            "--reference",
            str(path),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert np.array_equal(load_nifti(output / "resampled.nii.gz").array(), load_nifti(path).array())
    assert (output / "manifest.json").exists()
    result = CliRunner().invoke(app, ["mri", "inspect", "--input", str(tmp_path / "missing.nii")])
    assert result.exit_code == 1


def test_transform_serialization_and_independent_sitk_center(tmp_path):
    import SimpleITK as sitk
    from numpy.testing import assert_allclose

    from soma.imaging.phantoms import LANDMARKS_M

    native = sitk.Euler3DTransform()
    native.SetCenter((10.0, -20.0, 30.0))
    native.SetRotation(0.1, -0.05, 0.04)
    native.SetTranslation((2.0, -3.0, 1.0))
    converted = sitk_transform_to_ras(native, rigid=True)
    point = np.array([0.02, 0.01, -0.04])
    expected = np.array(native.TransformPoint(tuple(point * [-1000, -1000, 1000]))) * [
        -0.001,
        -0.001,
        0.001,
    ]
    assert_allclose(
        converted.matrix[:3, :3] @ point + converted.matrix[:3, 3], expected, atol=1e-14
    )
    f = asymmetric((0.003,) * 3)
    truth = known_transform()
    moving = transformed_asymmetric(f, truth)
    result = register(f, moving, RegistrationConfig(iterations=150))
    path = tmp_path / "transform"
    result.save(path)
    restored = sitk.ReadTransform(str(path / "fixed-to-moving-LPS-mm.tfm"))
    reloaded = sitk_transform_to_ras(restored, rigid=True)
    assert_allclose(reloaded.matrix, result.transform.matrix, atol=1e-14)
    assert transform_error(reloaded, truth, LANDMARKS_M)["median_landmark_TRE_m"] < 0.001


@pytest.mark.integration
def test_real_structural_inspection_and_source_compatibility():
    try:
        path, _ = cached_structural(Path("data/raw/mri"))
    except FileNotFoundError:
        pytest.skip("Explicitly cached SPM anatomy required; never fetch")
    v = load_nifti(path)
    assert v.shape == (256, 256, 54)
    assert v.metadata["qform_code"] == v.metadata["sform_code"] == 2
    assert v.metadata["slope"] == 0.125
    assert v.geometry()["axis_codes"] == ["L", "A", "S"]
    assert np.isfinite(v.array()).all()
    from soma.source.workflow import study_forward

    f = study_forward()
    assert f.diagnostics()["rank"] == 63
    assert f.matrix.shape == (64, 1284)
