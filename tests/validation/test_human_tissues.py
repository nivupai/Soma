"""Independent masked-metric and local-reference geometry/identity checks."""

import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.benchmarks.segmentation import LabelVolume, score, surfels
from soma.datasets.external_anatomy import TISSUES
from soma.datasets.human_mri import (
    access_metadata,
    align_t1,
    corner_displacement_mm,
    load_human,
    mapped_reference,
    safe_local_output,
    verify_inventory_inputs,
)
from soma.imaging.volumes import Volume
from soma.validation.human_tissues import human_configuration, predict_t1


def volume(data, subject="synthetic", affine=None):
    return Volume(
        np.asarray(data),
        np.diag([0.001, 0.001, 0.001, 1]) if affine is None else affine,
        "labels",
        {"subject": subject, "space": "native", "source_sha256": "synthetic-image"},
    )


def lv(data):
    return LabelVolume(
        volume(data),
        "synthetic",
        "native",
        {1: "test tissue"},
        {"source": "independent mathematical fixture"},
    )


def test_masked_overlap_specificity_and_volume_independent_counts():
    r = np.zeros((2, 2, 2), dtype=np.uint8)
    p = r.copy()
    r.ravel()[:2] = 1
    p.ravel()[[0, 2, 4, 5, 6, 7]] = 1
    valid = np.zeros_like(r)
    valid.ravel()[:4] = 1
    row = score(lv(p), lv(r), valid_mask=volume(valid))["labels"][0]
    # On four valid voxels: TP=FP=FN=TN=1. Four invalid predictions have no effect.
    for key in ["Dice", "sensitivity", "specificity"]:
        assert_allclose(row[key], 0.5)
    assert_allclose(row["Jaccard"], 1 / 3)
    assert_allclose(row["reference_volume_mm3"], 2)
    assert_allclose(row["prediction_volume_mm3"], 2)
    assert_allclose(row["signed_volume_error_mm3"], 0)


def test_no_artificial_surface_at_void_cut_independent_cube_area():
    mask = np.zeros((4, 4, 4), dtype=bool)
    mask[1:3, 1:3, 1:3] = True
    valid = np.ones_like(mask)
    valid[0, :, :] = False
    _, native = surfels(mask, np.diag([0.001, 0.001, 0.001, 1]))
    _, observed = surfels(mask, np.diag([0.001, 0.001, 0.001, 1]), valid_mask=valid)
    assert_allclose(native.sum(), 6 * 2 * 2)
    assert_allclose(observed.sum(), 5 * 2 * 2)


def test_unobserved_boundary_is_not_perfect_distance():
    x = np.ones((3, 3, 3), dtype=np.uint8)
    row = score(lv(x), lv(x), valid_mask=volume(x))["labels"][0]
    assert row["Dice"] == 1 and row["ASSD_mm"] is None and row["HD95_mm"] is None
    assert row["boundary_case"] == "unobserved_prediction_or_reference_boundary"
    assert row["boundaries"]["1.0"]["surface_Dice"] is None


@pytest.mark.parametrize("kind", ["subject", "grid", "nonbinary", "empty"])
def test_invalid_scoring_domains_rejected(kind):
    x = np.ones((3, 3, 3), dtype=np.uint8)
    m = volume(x)
    if kind == "subject":
        m = volume(x, subject="other")
    if kind == "grid":
        m = volume(x, affine=np.diag([0.002, 0.001, 0.001, 1]))
    if kind == "nonbinary":
        m = volume(x * 2)
    if kind == "empty":
        m = volume(x * 0)
    with pytest.raises(ValueError):
        score(lv(x), lv(x), valid_mask=m)


def test_excluded_label_does_not_create_mask_based_prediction():
    x = np.zeros((5, 5, 5), dtype=np.float32)
    x[1:4, 1:4, 1:4] = np.arange(27).reshape(3, 3, 3) + 2
    image = Volume(
        x,
        np.diag([0.001, 0.001, 0.001, 1]),
        "intensity",
        {"subject": "synthetic", "space": "native", "source_sha256": "intensity-only"},
    )
    first = predict_t1(image)
    ref = volume(np.ones((5, 5, 5), dtype=np.int16) * 7)
    mapped_reference(ref, "mrbrains13")
    second = predict_t1(image)
    assert_allclose(first.volume.array(), second.volume.array())
    assert first.provenance["truth_used"] is False
    assert first.provenance["input_sha256"] == "intensity-only"


def save_image(path, data, *, units="mm", qoffset=0.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    im = nib.Nifti1Image(np.asarray(data), np.diag([0.9375, 1.5, 0.9375, 1]))
    im.header.set_xyzt_units(units)
    im.set_sform(im.affine, code=1)
    if qoffset:
        q = im.affine.copy()
        q[0, 3] += qoffset
        im.set_qform(q, code=2)
    else:
        im.set_qform(None, code=0)
    nib.save(im, path)


def test_ibsr_explicit_singleton_and_units_override(tmp_path):
    p = tmp_path / "IBSR_99" / "IBSR_99_ana_strip.nii.gz"
    save_image(p, np.ones((3, 3, 3, 1), dtype=np.int16), units="unknown")
    v = load_human(p, dataset="ibsr-v2", subject="ibsr-v2:IBSR_99", role="intensity")
    assert v.shape == (3, 3, 3) and v.metadata["selected_frame"] == 0
    assert v.metadata["interpreted_spatial_units"] == "mm"
    assert_allclose(v.spacing_m, [0.0009375, 0.0015, 0.0009375])


def test_real_multiframe_ibsr_rejected(tmp_path):
    p = tmp_path / "IBSR_99_ana_strip.nii.gz"
    save_image(p, np.ones((3, 3, 3, 2), dtype=np.int16), units="unknown")
    with pytest.raises(ValueError, match="singleton"):
        load_human(p, dataset="ibsr-v2", subject="ibsr-v2:IBSR_99", role="intensity")


def test_filename_subject_mismatch_rejected(tmp_path):
    p = tmp_path / "IBSR_99_ana_strip.nii.gz"
    save_image(p, np.ones((3, 3, 3), dtype=np.int16))
    with pytest.raises(ValueError, match="identity"):
        load_human(p, dataset="ibsr-v2", subject="ibsr-v2:IBSR_98", role="intensity")


def test_hidden_partition_rejected_before_payload_read(tmp_path):
    p = tmp_path / "test" / "99" / "LabelsForTesting.nii"
    with pytest.raises(ValueError, match="training partition"):
        load_human(p, dataset="mrbrains13", subject="mrbrains13-training:99", role="labels")


def test_large_qform_sform_conflict_rejected(tmp_path):
    p = tmp_path / "training" / "99" / "T1.nii"
    save_image(p, np.ones((3, 3, 3), dtype=np.int16), qoffset=0.6)
    with pytest.raises(ValueError, match="qform/sform"):
        load_human(p, dataset="mrbrains13", subject="mrbrains13-training:99", role="intensity")


def test_unknown_native_code_rejected_before_integer_overflow(tmp_path):
    p = tmp_path / "training" / "99" / "LabelsForTraining.nii"
    save_image(p, np.ones((3, 3, 3), dtype=np.float32) * 65536)
    with pytest.raises(ValueError, match="Unknown native"):
        load_human(p, dataset="mrbrains13", subject="mrbrains13-training:99", role="labels")


def test_native_mapping_and_cerebellum_exclusion():
    values = np.arange(9, dtype=np.int16).reshape(3, 3, 1)
    canonical, valid = mapped_reference(volume(values), "mrbrains13")
    assert_allclose(canonical.array().ravel(), [0, 2, 2, 3, 3, 1, 1, 0, 0])
    assert_allclose(valid.array().ravel(), [1, 1, 1, 1, 1, 1, 1, 0, 0])
    with pytest.raises(ValueError):
        mapped_reference(volume(values), "ibsr-v2")


def test_intensity_roundoff_alignment_linear_independent_ramp():
    data = np.indices((5, 5, 5))[0].astype(float)
    a = np.diag([0.001, 0.001, 0.001, 1])
    b = a.copy()
    b[0, 3] = 0.00002
    image = Volume(data, a, "intensity", {"subject": "synthetic"})
    ref = volume(np.zeros_like(data, dtype=np.uint8), affine=b)
    result, receipt = align_t1(image, ref, dataset="mrbrains13")
    assert receipt["resampled"] and receipt["fitted_registration"] is False
    assert_allclose(receipt["maximum_corner_displacement_mm"], 0.02)
    assert_allclose(result.array()[2, 2, 2], 2.02, atol=1e-12)
    assert ref.affine_m[0, 3] == 0.00002
    with pytest.raises(ValueError):
        align_t1(image, ref, dataset="ibsr-v2")


def test_alignment_rejects_large_difference_or_mixed_identity():
    a = np.diag([0.001, 0.001, 0.001, 1])
    b = a.copy()
    b[0, 3] = 0.0001
    image = Volume(np.ones((3, 3, 3)), a, "intensity", {"subject": "synthetic"})
    with pytest.raises(ValueError):
        align_t1(image, volume(np.zeros((3, 3, 3), dtype=np.uint8), affine=b), dataset="mrbrains13")
    with pytest.raises(ValueError):
        align_t1(
            image,
            volume(np.zeros((3, 3, 3), dtype=np.uint8), subject="other"),
            dataset="mrbrains13",
        )


def test_corner_displacement_independent_translation():
    a = np.eye(4)
    b = a.copy()
    b[:3, 3] = [3, 4, 0]
    assert_allclose(corner_displacement_mm(a, b, (2, 3, 4)), 5.0)


def test_mutated_input_inventory_is_rejected(tmp_path):
    from soma.core.provenance import sha256

    p = tmp_path / "input.nii"
    p.write_bytes(b"original")
    inv = {"files": [{"path": str(p), "sha256": sha256(p)}]}
    verify_inventory_inputs(inv)
    p.write_bytes(b"modified")
    with pytest.raises(ValueError, match="Frozen input changed"):
        verify_inventory_inputs(inv)


def test_raw_output_in_source_tree_forbidden():
    with pytest.raises(ValueError, match="ignored"):
        safe_local_output(Path("docs/private-mri-output"))


def test_human_protocol_sealed():
    assert (
        human_configuration(Path("configs/human-tissues.yaml"))["MRBrainS_partition"] == "training"
    )
    with pytest.raises(ValueError):
        human_configuration(Path("configs/tissue-benchmark.yaml"))


def test_missing_local_readme_manifest_not_assumed_authorized(tmp_path):
    with pytest.raises(ValueError, match="Readme"):
        access_metadata(tmp_path, tmp_path)


@pytest.mark.integration
def test_actual_local_inventory_geometry_and_mapping():
    path = Path("reports/milestone11-human-inventory/inventory.json")
    if not path.exists():
        pytest.skip("Explicit local human data inventory required")
    inventory = json.loads(path.read_text())
    assert inventory["counts"] == {"ibsr_development": 18, "mrbrains_training_external": 5}
    assert inventory["test_payloads_read"] is False
    for dataset in ["ibsr-v2", "mrbrains13"]:
        r = next(r for r in inventory["subjects"] if r["dataset"] == dataset)
        image = load_human(
            Path(r["image"]), dataset=dataset, subject=r["subject"], role="intensity"
        )
        native = load_human(
            Path(r["reference"]), dataset=dataset, subject=r["subject"], role="labels"
        )
        aligned, receipt = align_t1(image, native, dataset=dataset)
        assert aligned.same_grid(native)
        canonical, valid = mapped_reference(native, dataset)
        assert set(np.unique(canonical.array())).issubset(TISSUES.keys() | {0})
        assert valid.shape == aligned.shape


def test_complete_prediction_loss_remains_visible_in_volume_plot(tmp_path):
    from soma.validation.human_plots import cohort_figures

    rows = [
        {
            "dataset": "synthetic fixture",
            "labels": [
                {
                    "Dice": 0.0,
                    "ASSD_mm": None,
                    "HD95_mm": None,
                    "signed_relative_volume_error": -1.0,
                },
                {
                    "Dice": None,
                    "ASSD_mm": None,
                    "HD95_mm": None,
                    "signed_relative_volume_error": None,
                },
                {"Dice": 1.0, "ASSD_mm": 0.0, "HD95_mm": 0.0, "signed_relative_volume_error": 0.0},
            ],
        }
    ]
    cohort_figures(tmp_path, rows)
    with np.load(tmp_path / "subject-tissue-metrics.npz", allow_pickle=False) as a:
        assert a["signed_relative_volume_error"][0, 0] == -1
        assert a["signed_relative_volume_error"][0, 1] == -2
        assert a["undefined_relative_volume_sentinel"] == -2
