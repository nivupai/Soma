import nibabel as nib
import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.geometry import Frame, Points
from soma.geometry.coordinates import VoxelMap, ras_lps, transform_vectors
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.orientation import reorient
from soma.imaging.registration import from_sitk, to_sitk
from soma.imaging.volumes import Volume


@pytest.mark.parametrize(
    "linear",
    [
        np.eye(3),
        np.diag([-1.0, 2, 3]),
        np.eye(3)[[2, 0, 1]],
        np.array([[1.0, 0.2, 0], [0, 2, 0.1], [0, 0, 3]]),
    ],
)
def test_voxel_world_independent(linear):
    a = np.eye(4)
    a[:3, :3] = linear * 0.001
    a[:3, 3] = [0.02, -0.03, 0.01]
    grid = VoxelMap(a, "test")
    ijk = np.random.default_rng(1).uniform(-2, 30, (20, 3))
    points = grid.to_world(ijk)
    expected = nib.affines.apply_affine(a, ijk)
    assert_allclose(points.xyz, expected, atol=1e-16)
    assert_allclose(grid.to_voxel(points), ijk, atol=1e-12)
    lps = ras_lps().apply(points)
    assert_allclose(lps.xyz, points.xyz * [-1, -1, 1])
    assert_allclose(ras_lps().inverse().apply(lps).xyz, points.xyz)
    with pytest.raises(ValueError):
        grid.to_voxel(lps)


def test_vectors_normals_and_storage_reorientation():
    a = np.eye(4)
    a[:3, :3] = [[2, 0.3, 0], [0, 1, 0], [0, 0, 3]]
    tangent = np.array([[1.0, 0, 0]])
    normal = np.array([[0.0, 1, 0]])
    assert_allclose(
        np.sum(transform_vectors(a, tangent) * transform_vectors(a, normal, normals=True)),
        0,
        atol=1e-14,
    )
    a = np.diag([-0.002, 0.003, 0.004, 1])
    a[:3, 3] = [0.01, -0.02, -0.03]
    v = Volume(np.arange(24).reshape(2, 3, 4), a)
    r = reorient(v)
    assert nib.aff2axcodes(r.affine_m) == ("R", "A", "S")
    assert_allclose(r.array()[0, 0, 0], v.array()[-1, 0, 0])
    assert_allclose(
        r.grid.to_world(np.array([[0.0, 0, 0]])).xyz, v.grid.to_world(np.array([[1.0, 0, 0]])).xyz
    )
    assert np.shares_memory(v.array(), r.array())
    with pytest.raises(ValueError):
        Points(np.ones((1, 3)), Frame.VOXEL)


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("units,factor", [("mm", 0.001), ("meter", 1), ("micron", 1e-6)])
def test_nifti_roundtrip_selection_units(tmp_path, version, units, factor):
    a = np.diag([0.001, 0.002, 0.003, 1])
    raw = a.copy()
    raw[:3] /= factor
    cls = nib.Nifti1Image if version == 1 else nib.Nifti2Image
    image = cls(np.ones((4, 5, 6), dtype=np.int16), raw)
    image.header.set_xyzt_units(units)
    image.set_qform(raw, 2)
    image.set_sform(raw, 1)
    path = tmp_path / "image.nii"
    nib.save(image, path)
    v = load_nifti(path)
    assert v.dtype == np.dtype("int16")
    assert_allclose(v.affine_m, a, atol=1e-10)
    assert v.metadata["selected_affine_source"] == "sform"
    assert not isinstance(v.data, np.ndarray)
    out = tmp_path / "copy.nii"
    save_nifti(v, out)
    assert_allclose(load_nifti(out).array(), v.array())
    with pytest.raises(FileExistsError):
        save_nifti(v, out)


def test_conflict_unknown_units_fallback_and_scaling(tmp_path):
    p = tmp_path / "a.nii"
    a = np.eye(4)
    image = nib.Nifti1Image(np.ones((4, 5, 6), dtype=np.int16), a)
    nib.save(image, p)
    with pytest.raises(ValueError, match="units"):
        load_nifti(p)
    image.header.set_xyzt_units("mm")
    image.set_qform(a, 1)
    b = a.copy()
    b[0, 3] = 10
    image.set_sform(b, 2)
    image.header.set_slope_inter(2, 3)
    nib.save(image, p)
    with pytest.raises(ValueError, match="Ambiguous"):
        load_nifti(p)
    with pytest.warns(UserWarning):
        v = load_nifti(p, policy="nibabel")
    assert v.metadata["selected_affine_source"] == "sform"
    assert_allclose(v.array(), 5)
    assert v.metadata["slope"] == 2
    with pytest.warns(UserWarning):
        q = load_nifti(p, policy="qform")
    assert q.affine_m[0, 3] == 0
    image.set_qform(None, 0)
    image.set_sform(None, 0)
    nib.save(image, p)
    with pytest.raises(ValueError):
        load_nifti(p)
    with pytest.warns(UserWarning):
        v = load_nifti(p, policy="nibabel")
    assert v.metadata["selected_affine_source"] == "nibabel_base_affine"


def test_4d_requires_explicit_lazy_frame(tmp_path):
    p = tmp_path / "4d.nii"
    image = nib.Nifti1Image(np.stack([np.zeros((3, 4, 5)), np.ones((3, 4, 5))], axis=-1), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, p)
    with pytest.raises(ValueError, match="frame"):
        load_nifti(p)
    v = load_nifti(p, frame=1)
    assert v.shape == (3, 4, 5)
    assert_allclose(v.array(), 1)
    with pytest.raises(ValueError):
        load_nifti(p, frame=2)


@pytest.mark.parametrize(
    "bad", [np.zeros((4, 4)), np.diag([1.0, 1, 1e-12, 1]), np.full((4, 4), np.nan)]
)
def test_invalid_affines(bad):
    with pytest.raises(ValueError):
        Volume(np.ones((4, 4, 4)), bad)


def test_sitk_axis_lps_and_spacing_agreement():
    a = np.diag([-0.001, 0.002, 0.003, 1])
    a[:3, 3] = [0.02, -0.03, 0.01]
    v = Volume(np.arange(120, dtype=np.float32).reshape(4, 5, 6), a)
    image = to_sitk(v)
    r = from_sitk(image)
    assert_allclose(v.array(), r.array())
    assert_allclose(v.affine_m, r.affine_m, atol=1e-15)
    ijk = (2, 3, 4)
    assert_allclose(
        np.array(image.TransformIndexToPhysicalPoint(ijk)) / 1000,
        v.grid.to_world(np.array([ijk])).xyz[0] * [-1, -1, 1],
        atol=1e-15,
    )
    shear = a.copy()
    shear[0, 1] = 0.0003
    with pytest.raises(ValueError, match="orthogonal"):
        to_sitk(Volume(v.array(), shear))


def test_truncated_nifti_and_invalid_volume_shape(tmp_path):
    p = tmp_path / "truncated.nii"
    image = nib.Nifti1Image(np.ones((8, 8, 8), dtype=np.int16), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, p)
    p.write_bytes(p.read_bytes()[:-30])
    with pytest.raises(ValueError, match="available NIfTI"):
        load_nifti(p)
    with pytest.raises(ValueError):
        Volume(np.ones((2, 2, 2, 2)), np.diag([0.001, 0.001, 0.001, 1]))
    with pytest.raises(ValueError):
        VoxelMap(np.eye(4), "")


def test_sheared_nifti_save_has_no_approximate_qform(tmp_path):
    a = np.diag([0.001, 0.002, 0.003, 1])
    a[0, 1] = 0.0002
    v = Volume(np.zeros((4, 5, 6), dtype=np.float32), a)
    p = tmp_path / "sheared.nii"
    save_nifti(v, p)
    r = load_nifti(p)
    assert r.metadata["qform_code"] == 0
    assert r.metadata["sform_code"] == 2
    assert_allclose(r.affine_m, a, atol=1e-10)


def test_sitk_boundary_preserves_large_integer_intensities():
    data = np.full((4, 4, 4), 2**40 + 1, dtype=np.int64)
    v = Volume(data, np.diag([0.001, 0.001, 0.001, 1]))
    r = from_sitk(to_sitk(v))
    assert r.array().dtype == data.dtype
    assert np.array_equal(r.array(), data)


@pytest.mark.parametrize("dtype", [complex, object])
def test_non_scalar_real_dtype_rejected(dtype):
    with pytest.raises(ValueError, match="real scalar"):
        Volume(np.ones((3, 3, 3), dtype=dtype), np.diag([0.001, 0.001, 0.001, 1]))


def test_unexpected_storage_orientation_is_diagnostic():
    from soma.imaging.validation import validate_volume

    v = Volume(np.zeros((3, 3, 3)), np.diag([-0.001, 0.001, 0.001, 1]))
    result = validate_volume(v, expected_axis_codes=("R", "A", "S"))
    assert any("unexpected_storage_axis" in item for item in result["diagnostics"])
    assert result["valid"]


@pytest.mark.parametrize("version", [1, 2])
def test_write_binary_mask_and_int64_with_explicit_nifti_version(tmp_path, version):
    a = np.diag([0.001, 0.002, 0.003, 1])
    for name, data in [
        ("boolean", np.ones((3, 3, 3), dtype=bool)),
        ("int64", np.full((3, 3, 3), 2**40 + 1, dtype=np.int64)),
    ]:
        path = tmp_path / f"{name}.nii"
        save_nifti(Volume(data, a, "labels"), path, version=version)
        loaded = load_nifti(path, kind="labels")
        assert np.array_equal(loaded.array(), data)
        assert loaded.metadata["nifti_class"] == f"Nifti{version}Image"
