"""External evidence, independence, split, and access adversarial cases."""

import gzip
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
from numpy.testing import assert_allclose
from typer.testing import CliRunner

from soma.benchmarks.segmentation import LabelVolume
from soma.cli import app
from soma.core.provenance import sha256
from soma.datasets.external_anatomy import (
    TISSUES,
    ingest_mrbrains13_training,
    inspect_sci,
    local_reference_manifest,
    nrrd_volume,
    read_nrrd,
)
from soma.datasets.references import load_reference
from soma.validation.cohort import (
    backend_prediction,
    evaluate_subject,
    subject_interval,
    validate_split,
)
from soma.validation.conductors import require_bem_materials
from soma.validation.config import configuration


def save(path, data):
    image = nib.Nifti1Image(np.asarray(data), np.diag([1.0, 1.0, 2.0, 1.0]))
    image.header.set_xyzt_units("mm")
    nib.save(image, path)


def fixture_record(tmp_path):
    values = np.zeros((8, 8, 8), dtype=np.int16)
    values[1:3, 1:7, 1:7] = 10
    values[3:5, 1:7, 1:7] = 20
    values[5:7, 1:7, 1:7] = 40
    labels = np.zeros_like(values)
    labels[values == 10] = 1
    labels[values == 20] = 2
    labels[values == 40] = 3
    labels[2, 2, 2] = 2
    image = tmp_path / "T1.nii"
    reference = tmp_path / "reference.nii"
    save(image, values)
    save(reference, labels)
    return {
        "subject": "IBSR_01",
        "split": "development",
        "space": "subject-native",
        "image": str(image),
        "reference": str(reference),
        "modality": "T1",
        "acquisition": {"scanner": "unknown", "protocol": "unknown"},
        "reference_ontology": TISSUES,
        "reference_provenance": {"evidence_type": "synthetic test oracle, not human"},
    }


def test_actual_independent_baseline_and_metric_oracle(tmp_path):
    r = fixture_record(tmp_path)
    row, arrays = evaluate_subject(r)
    assert row["prediction_provenance"]["truth_used"] is False
    assert row["reference_provenance"]["sha256"] != row["prediction_provenance"]["input_sha256"]
    # CSF has exactly one missed voxel; no tuning from reference.
    assert_allclose(row["labels"][0]["Dice"], 142 / 143)
    assert row["registration_performed"] is False
    assert arrays["reference_slice"].shape == (8, 8)


@pytest.mark.parametrize(
    "development,holdout,records",
    [
        (["x"], ["x"], []),
        (["a"], ["b"], [{"subject": "b", "split": "development"}]),
        (
            ["a"],
            ["b"],
            [{"subject": "a", "split": "development"}, {"subject": "a", "split": "development"}],
        ),
        (["a"], ["b"], [{"subject": "a", "split": "development", "reference_subject": "b"}]),
        (["a"], ["b"], [{"subject": "a", "split": "training"}]),
    ],
)
def test_holdout_adversarial_rejections(development, holdout, records):
    with pytest.raises(ValueError):
        validate_split(records, development, holdout)


def test_split_valid():
    validate_split(
        [{"subject": "a", "split": "development"}, {"subject": "b", "split": "holdout"}],
        ["a"],
        ["b"],
    )


def test_ref_is_not_image(tmp_path):
    r = fixture_record(tmp_path)
    r["image"] = r["reference"]
    with pytest.raises(ValueError, match="independent MRI"):
        evaluate_subject(r)


def test_unknown_tissue_ontology(tmp_path):
    r = fixture_record(tmp_path)
    r["reference_ontology"] = {1: "skull"}
    with pytest.raises(ValueError, match="ontology"):
        evaluate_subject(r)


def test_missing_backend_metadata_rejected(tmp_path):
    r = fixture_record(tmp_path)
    ref = load_reference(Path(r["reference"]), kind="labels", subject="s", space="native")
    lv = LabelVolume(
        ref,
        "s",
        "native",
        TISSUES,
        {"path": r["reference"], "sha256": sha256(Path(r["reference"]))},
    )
    with pytest.raises(ValueError, match="provenance"):
        backend_prediction(Path(r["reference"]), {}, lv)


def test_self_reference_rejected_by_hash_not_just_path(tmp_path):
    r = fixture_record(tmp_path)
    ref = load_reference(Path(r["reference"]), kind="labels", subject="s", space="native")
    lv = LabelVolume(
        ref,
        "s",
        "native",
        TISSUES,
        {"path": r["reference"], "sha256": sha256(Path(r["reference"]))},
    )
    copied = tmp_path / "copy.nii"
    copied.write_bytes(Path(r["reference"]).read_bytes())
    backend = {
        "tool": "test",
        "version": "1",
        "model_version": "none",
        "input_contrast": "T1",
        "label_mapping": {0: 0, 1: 1, 2: 2, 3: 3},
        "transform_history": [],
        "options": {},
        "runtime_s": 1,
        "truth_used": False,
        "input_sha256": sha256(Path(r["image"])),
    }
    with pytest.raises(ValueError, match="own prediction"):
        backend_prediction(copied, backend, lv)


def test_subject_bootstrap_uses_subject_not_voxel():
    a = subject_interval([0.2, 0.4, 0.8])
    b = subject_interval([0.2, 0.4, 0.8])
    assert a == b and a["n_subjects"] == 3
    assert_allclose(a["mean"], 1.4 / 3)
    assert subject_interval([0.3])["CI95"] is None


def write_nrrd(path, space="left-posterior-superior", units='"mm" "mm" "mm"', data=None):
    values = np.arange(24, dtype=np.uint8).reshape(2, 3, 4, order="F") if data is None else data
    header = (
        f"NRRD0005\ntype: unsigned char\ndimension: 3\nsizes: 2 3 4\n"
        f"space: {space}\nspace units: {units}\n"
        "space directions: (1,0,0) (0,2,0) (0,0,3)\n"
        "space origin: (10,20,30)\nencoding: gzip\n\n"
    ).encode()
    path.write_bytes(header + gzip.compress(values.tobytes(order="F")))
    return values


def test_nrrd_geometry_and_axis_order(tmp_path):
    p = tmp_path / "image.nrrd"
    expected = write_nrrd(p)
    actual, h = read_nrrd(p)
    assert_allclose(actual, expected)
    v = nrrd_volume(p)
    assert_allclose(
        v.affine_m,
        np.array([[-0.001, 0, 0, -0.01], [0, -0.002, 0, -0.02], [0, 0, 0.003, 0.03], [0, 0, 0, 1]]),
    )


def test_generic_right_handed_frame_not_anatomical_frame(tmp_path):
    p = tmp_path / "labels.nrrd"
    write_nrrd(p, space="3D-right-handed")
    with pytest.raises(ValueError, match="unestablished"):
        nrrd_volume(p)
    with pytest.raises(ValueError, match="evidence"):
        nrrd_volume(p, space_override="left-posterior-superior")


def test_unknown_units_require_evidence(tmp_path):
    p = tmp_path / "labels.nrrd"
    write_nrrd(p, units="")
    with pytest.raises(ValueError, match="units"):
        nrrd_volume(p)
    assert nrrd_volume(
        p, units_override="mm", justification="test fixture documented mm"
    ).shape == (2, 3, 4)


def test_nrrd_truncated_data(tmp_path):
    p = tmp_path / "bad.nrrd"
    write_nrrd(p, data=np.ones(2, dtype=np.uint8))
    with pytest.raises(ValueError, match="payload"):
        read_nrrd(p)


def test_missing_reference_is_not_success(tmp_path):
    r = inspect_sci(tmp_path)
    assert r["status"] == "missing_assets" and r["BEM_readiness"] == "INDETERMINATE"
    assert local_reference_manifest(tmp_path / "missing.json")["status"] == "unavailable"


@pytest.mark.parametrize(
    "representation,ids,frame",
    [
        ("tetrahedral FEM", [1, 3, 4], True),
        ("three-layer triangular BEM", [1, 2, 3], True),
        ("three-layer triangular BEM", [1, 3, 4], False),
    ],
)
def test_fem_bem_and_frame_incompatibility(representation, ids, frame):
    with pytest.raises(ValueError):
        require_bem_materials(representation, ids, frame)


def test_bem_contract():
    require_bem_materials("three-layer triangular BEM", [1, 3, 4], True)


def test_frozen_configs_and_no_unsealed_overrides(tmp_path):
    cfg = configuration(Path("configs/anatomical-holdout.yaml"))
    assert cfg["holdout_subjects"] == ["IBSR_02", "IBSR_03", "IBSR_04"]
    with pytest.raises(ValueError):
        configuration(tmp_path / "unsealed.yaml")


def test_missing_local_authorization(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"dataset": "mrbrains13", "subjects": []}))
    with pytest.raises(ValueError, match="authorized"):
        local_reference_manifest(p)


def test_cli_inspect_offline(tmp_path, monkeypatch):
    import soma.datasets.external_anatomy as external

    original = external.inspect_sci
    monkeypatch.setattr(external, "inspect_sci", lambda: original(tmp_path))
    result = CliRunner().invoke(app, ["mri", "references", "inspect", "--dataset", "sci-head"])
    assert result.exit_code == 0 and "BEM_readiness" in result.stdout


def test_mrbrains_hidden_labels_not_ingested(tmp_path):
    with pytest.raises(ValueError, match="training labels"):
        ingest_mrbrains13_training(
            tmp_path / "T1.nii",
            tmp_path / "HiddenTestLabels.nii",
            subject="s",
            split="holdout",
            authorization="authorized",
            native_label_names={},
        )


def test_mrbrains_mapping_and_explicit_exclusions(tmp_path):
    image = tmp_path / "T1.nii"
    labels = tmp_path / "LabelsForTraining.nii"
    values = np.arange(9, dtype=np.int16).reshape(3, 3, 1)
    save(image, values * 10)
    save(labels, values)
    names = {
        0: "background",
        1: "cortical gray matter",
        2: "basal ganglia",
        3: "white matter",
        4: "white matter lesions",
        5: "peripheral CSF",
        6: "lateral ventricles",
        7: "cerebellum",
        8: "brainstem",
    }
    _, v, excluded, receipt = ingest_mrbrains13_training(
        image,
        labels,
        subject="s",
        split="development",
        authorization="authorized local fixture",
        native_label_names=names,
    )
    assert_allclose(v.array().ravel(), [0, 2, 2, 3, 3, 1, 1, 0, 0])
    assert_allclose(excluded.ravel(), [0, 0, 0, 0, 0, 0, 0, 1, 1])
    assert receipt["exclusion_required_for_scoring"]


@pytest.mark.integration
def test_actual_sci_assets_opt_in():
    root = Path("data/raw/references/sci-head")
    if not (root / "Segmentation/HeadSegmentation.nrrd").exists():
        pytest.skip("Explicit SCI acquisition required")
    r = inspect_sci(root)
    assert r["status"] == "available_with_unresolved_geometry"
    assert r["assets"]["T1"]["shape"] == [208, 256, 256]
    assert set(r["assets"]["segmentation"]["label_counts"]) == set(map(str, range(1, 9)))
    assert r["BEM_readiness"] == "INDETERMINATE"


def test_same_image_under_different_subject_ids_rejected(tmp_path):
    a = fixture_record(tmp_path)
    b = {**a, "subject": "IBSR_02", "split": "holdout"}
    with pytest.raises(ValueError, match="Repeated source assets"):
        validate_split([a, b], ["IBSR_01"], ["IBSR_02"])


def test_missing_cohort_cli_records_actual_missingness(tmp_path, monkeypatch):
    import soma.validation.cohort as cohort

    monkeypatch.setattr(
        cohort,
        "local_reference_manifest",
        lambda _: {"subjects": [], "diagnostic": "offline fixture unavailable"},
    )
    result = CliRunner().invoke(
        app, ["experiments", "anatomical-holdout", "--output", str(tmp_path / "report")]
    )
    assert result.exit_code == 0
    summary = json.loads((tmp_path / "report/summary.json").read_text())
    assert summary["status"] == "incomplete_reference_evaluation"
    assert summary["macro_Dice"] is None and len(summary["missing_subjects"]) == 3
    assert summary["population_generalization_claimed"] is False
    assert (tmp_path / "report/tissue-subject-variability.npz").exists()


def test_m11_source_config_respects_historical_seal_api():
    from soma.source.workflow import sealed_config

    assert sealed_config(Path("configs/source-priors.yaml"))["milestone"] == 11


def test_nrrd_dimension_budget_uses_unbounded_integer_arithmetic(tmp_path):
    p = tmp_path / "huge.nrrd"
    p.write_bytes(
        b"NRRD0005\ntype: unsigned char\ndimension: 3\n"
        b"sizes: 99999999999 99999999999 99999999999\nencoding: raw\n\n"
    )
    with pytest.raises(ValueError, match="budget"):
        read_nrrd(p)


def test_undeclared_native_reference_codes_rejected(tmp_path):
    r = fixture_record(tmp_path)
    data = np.asarray(nib.load(r["reference"]).dataobj).copy()
    data[1, 1, 1] = 7
    save(r["reference"], data)
    with pytest.raises(ValueError, match="Undeclared native reference labels"):
        evaluate_subject(r)


def test_reference_copy_with_changed_header_still_rejected(tmp_path):
    r = fixture_record(tmp_path)
    ref = load_reference(Path(r["reference"]), kind="labels", subject="s", space="native")
    reference = LabelVolume(
        ref,
        "s",
        "native",
        TISSUES,
        {"path": r["reference"], "sha256": sha256(Path(r["reference"]))},
    )
    image = nib.load(r["reference"])
    image.header["descrip"] = b"independent-looking filename is not independent data"
    path = tmp_path / "changed-header.nii"
    nib.save(image, path)
    assert sha256(path) != sha256(Path(r["reference"]))
    backend = {
        "tool": "test",
        "version": "1",
        "model_version": "none",
        "input_contrast": "T1",
        "label_mapping": {0: 0, 1: 1, 2: 2, 3: 3},
        "transform_history": [],
        "options": {},
        "runtime_s": 1,
        "truth_used": False,
        "input_sha256": sha256(Path(r["image"])),
    }
    with pytest.raises(ValueError, match="Reference-identical label content"):
        backend_prediction(path, backend, reference)
