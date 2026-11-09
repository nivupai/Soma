import gzip
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose
from typer.testing import CliRunner

from soma.benchmarks.offgrid import (
    ContinuousDipole,
    direction,
    evaluate_forward,
    offgrid,
    reconstruction_metrics,
    reconstruction_operator,
    source_grid,
)
from soma.cli import app
from soma.datasets.references import RemoteZip, validate_minc_gzip
from soma.geometry import Frame, Points


@pytest.mark.parametrize("failure", ["frame", "orientation", "moment", "subject"])
def test_continuous_dipole_contracts(failure):
    point = Points(np.array([[0.01, 0.02, 0.03]]), Frame.HEAD if failure == "frame" else Frame.MRI)
    with pytest.raises(ValueError):
        ContinuousDipole(
            point,
            [0, 0, 2] if failure == "orientation" else [0, 0, 1],
            0 if failure == "moment" else 1e-8,
            "" if failure == "subject" else "s",
        )


def test_offgrid_location_is_independent_and_frame_checked():
    grid = source_grid(0.02)
    point = np.array([[0.0183, 0.0091, 0.0527]])
    dipole = ContinuousDipole(Points(point, Frame.MRI), direction(point[0]), 1e-8)
    d, i = offgrid(dipole, grid)
    independent = np.linalg.norm(grid.xyz - point, axis=1)
    assert_allclose(d, independent.min())
    assert i == int(independent.argmin())
    on = ContinuousDipole(Points(grid.xyz[[0]], Frame.MRI), direction(grid.xyz[0]), 1e-8)
    with pytest.raises(ValueError, match="coincides"):
        offgrid(on, grid)
    with pytest.raises(ValueError):
        offgrid(dipole, Points(grid.xyz, Frame.HEAD))
    with pytest.raises(ValueError):
        offgrid(dipole, grid, subject="unrelated")


def test_orientation_and_depth_are_physical():
    p = np.array([0.01, 0.02, 0.04])
    normal = direction(p)
    rotated = direction(p, 30)
    assert_allclose(np.linalg.norm(rotated), 1)
    assert_allclose(normal @ rotated, np.cos(np.pi / 6))
    assert 0.08 - np.linalg.norm(p) > 0.08 - np.linalg.norm(p * 1.2)


def test_separate_analytical_forward_and_geometric_lower_bound():
    grid = source_grid(0.03)
    point = Points(np.array([[0.0183, 0.0091, 0.0527]]), Frame.MRI)
    dipole = ContinuousDipole(point, direction(point.xyz[0]), 1e-8)
    distance, nearest = offgrid(dipole, grid)
    truth, rt = evaluate_forward(point)
    recon, rr = evaluate_forward(grid)
    assert rt["forward"]["cache_key"] != rr["forward"]["cache_key"]
    for orientation in ["fixed", "free"]:
        W, L, diag = reconstruction_operator(recon, grid, orientation=orientation)
        clean = truth @ (dipole.orientation * dipole.moment_Am)
        estimate = W @ clean[:, None]
        metrics = reconstruction_metrics(estimate, L, clean[:, None], dipole, grid, nearest)
        assert metrics["peak_error_mm"][0] + 1e-9 >= distance * 1000
        assert diag["rank"] <= 23 and np.isfinite(metrics["nearest_vertex_amplitude_ratio"]).all()
    assert_allclose(recon.sum(axis=0), 0, atol=1e-10)
    with pytest.raises(ValueError):
        reconstruction_operator(recon, grid, orientation="magnitude")


def test_deterministic_continuous_source_and_physical_cache():
    point = Points(np.array([[0.01, 0.02, 0.04]]), Frame.MRI)
    a, r = evaluate_forward(point)
    b, s = evaluate_forward(point)
    assert_allclose(a, b, atol=0, rtol=0)
    assert s["forward"]["hit"]
    changed, _ = evaluate_forward(point, sigmas=(0.3, 0.012, 0.3))
    assert np.linalg.norm(changed - a) > 0


def test_empty_or_html_gzip_is_not_a_reference_image():
    for data in [b"<html>", gzip.compress(b""), gzip.compress(b"<html>error</html>")]:
        with pytest.raises(ValueError):
            validate_minc_gzip(data)
    validate_minc_gzip(gzip.compress(b"CDF\x01header"))


def test_range_reader_refuses_unsafe_seeks_before_network():
    remote = RemoteZip("https://example.invalid/data", 100)
    with pytest.raises(ValueError):
        remote.seek(-1)
    with pytest.raises(ValueError):
        remote.seek(101)


@pytest.mark.parametrize(
    "args",
    [
        ["mri", "references", "list"],
        ["mri", "references", "fetch", "--help"],
        ["mri", "benchmark-segmentation", "--help"],
        ["mri", "benchmark-surfaces", "--help"],
        ["anatomy", "repair-audit", "--help"],
        ["source", "offgrid", "--help"],
        ["source", "grid-convergence", "--help"],
    ],
)
def test_new_cli_offline(args):
    assert CliRunner().invoke(app, args).exit_code == 0


@pytest.mark.integration
def test_actual_reference_files_and_preserved_native_label_ids():
    from soma.datasets.references import ROOT, load_reference, read_cortical_surface

    if not (ROOT / "mindboggle/selection.json").exists():
        pytest.skip("Explicit downloaded references required")
    truth = load_reference(
        ROOT / "brainweb/phantom_1.0mm_normal_crisp.mnc.gz",
        kind="labels",
        subject="normal",
        space="Talairach",
    )
    assert int(np.sum(truth.array() == 2)) == 902912
    base = ROOT / "mindboggle/selected/NKI-RS-22_volumes/NKI-RS-22-11"
    labels = load_reference(
        base / "labels.DKT31.manual.nii.gz",
        kind="labels",
        subject="NKI-RS-22-11",
        space="native",
        units_override="mm",
    )
    assert labels.dtype.kind in "iu" and 1002 in np.unique(labels.array())
    path = ROOT / "mindboggle/surfaces/NKI-RS-22_surfaces/NKI-RS-22-11/lh.labels.DKT31.manual.vtk"
    surface = read_cortical_surface(path, "NKI-RS-22-11")
    assert len(surface["manual_labels"]) == len(surface["points_as_stored_mm"])
    assert surface["faces"].shape[1] == 3
    with pytest.raises(ValueError):
        read_cortical_surface(path, "unrelated")


@pytest.mark.integration
def test_real_participant_continuous_BEM_is_separate_from_source_grid(tmp_path):
    from soma.benchmarks.config import configuration
    from soma.benchmarks.source_workflows import realistic_example
    from soma.datasets.matched import SampleAssets

    if not SampleAssets().raw_path.exists():
        pytest.skip("Explicit matched sample cache required")
    result = realistic_example(configuration(Path("configs/offgrid.yaml")), tmp_path)
    assert result["status"] == "conditional_BEM_complete" and not result["failures"]
    assert len(result["rows"]) == 32
    for row in result["rows"]:
        metric = row["metrics"]
        assert metric["peak_error_mm"]["mean"] + 1e-6 >= metric["nearest_grid_mm"]["mean"] > 0.5
    assert result["anatomical_readiness"] == "INDETERMINATE"


def test_range_reader_never_accepts_a_full_response(monkeypatch):
    import urllib.request

    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, *args):
            raise AssertionError("Must reject before reading full object")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: Response())
    with pytest.raises(ValueError, match="honor"):
        RemoteZip("https://example.invalid/data", 100).read(10)


def test_float_reference_codes_are_verified_not_thresholded(tmp_path):
    import nibabel as nib

    from soma.datasets.references import load_reference

    path = tmp_path / "labels.nii"
    image = nib.Nifti1Image(np.full((2, 2, 2), 2.0, dtype=np.float32), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, path)
    value = load_reference(path, kind="labels", subject="s", space="native")
    assert value.dtype.kind in "iu" and np.all(value.array() == 2)
    image = nib.Nifti1Image(np.full((2, 2, 2), 2.1, dtype=np.float32), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, path)
    with pytest.raises(ValueError, match="integer codes"):
        load_reference(path, kind="labels", subject="s", space="native")


def test_protocol_and_installed_version_match_source():
    import tomllib
    from importlib.metadata import version

    import soma
    from soma.benchmarks.config import configuration

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert version("soma-neuro") == soma.__version__ == project["version"]
    assert configuration(Path("configs/offgrid.yaml"))["offgrid_tolerance_m"] == 0.0005
    with pytest.raises(ValueError):
        configuration(Path("configs/inverse-audit.yaml"))


@pytest.mark.parametrize("unit,spacing", [("meter", 0.01), ("micron", 10000.0)])
def test_reference_loader_honors_coded_physical_units(tmp_path, unit, spacing):
    import nibabel as nib

    from soma.datasets.references import load_reference

    path = tmp_path / "reference.nii"
    image = nib.Nifti1Image(
        np.ones((2, 2, 2), dtype=np.int16), np.diag([spacing, spacing, spacing, 1.0])
    )
    image.header.set_xyzt_units(unit)
    nib.save(image, path)
    result = load_reference(path, kind="labels", subject="s", space="RAS-native")
    assert_allclose(result.spacing_m, 0.01, rtol=1e-7)


def test_uncoded_reference_units_require_explicit_override(tmp_path):
    import nibabel as nib

    from soma.datasets.references import load_reference

    path = tmp_path / "reference.nii"
    nib.save(nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.int16), np.eye(4)), path)
    with pytest.raises(ValueError, match="spatial units"):
        load_reference(path, kind="labels", subject="s", space="native")
    result = load_reference(path, kind="labels", subject="s", space="native", units_override="mm")
    assert_allclose(result.spacing_m, 0.001)
