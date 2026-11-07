import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.benchmarks.segmentation import LabelVolume, intensity_baseline, score, surfels
from soma.imaging.resampling import resample
from soma.imaging.volumes import Volume


def labels(data, *, subject="s", space="native", ontology=None, affine=None):
    return LabelVolume(
        Volume(
            np.asarray(data, dtype=np.int16),
            np.diag([0.001, 0.001, 0.001, 1.0]) if affine is None else affine,
            "labels",
        ),
        subject,
        space,
        ontology or {1: "region"},
        {"source": "analytic independent fixture"},
    )


def test_overlap_exact_set_oracle_and_volume():
    a = np.array([1, 1, 0, 0, 0, 0, 0, 0]).reshape(2, 2, 2)
    b = np.array([1, 0, 1, 0, 0, 0, 0, 0]).reshape(2, 2, 2)
    row = score(labels(a), labels(b))["labels"][0]
    assert row["Dice"] == 0.5 and row["Jaccard"] == 1 / 3
    assert row["sensitivity"] == 0.5 and row["specificity"] == 5 / 6
    geometry = score(labels(a), labels(b))["reference_geometry"]
    assert_allclose(geometry["spacing_m"], 0.001)
    assert_allclose(row["prediction_volume_mm3"], 2)
    assert_allclose(row["absolute_volume_error_mm3"], 0)


@pytest.mark.parametrize(
    "prediction,reference,case,dice",
    [(0, 0, "absent_both", None), (0, 1, "prediction_absent", 0), (1, 0, "reference_absent", 0)],
)
def test_empty_behavior_explicit(prediction, reference, case, dice):
    p = np.full((2, 2, 2), prediction)
    r = np.full((2, 2, 2), reference)
    result = score(labels(p), labels(r))
    row = result["labels"][0]
    assert row["case"] == case and row["Dice"] == dice
    assert row["Hausdorff_mm"] is None and row["HD95_mm"] is None
    assert result["macro_Dice"] == dice


@pytest.mark.parametrize("change", ["subject", "space", "ontology", "grid"])
def test_deceptive_alignment_or_ontology_match_rejected(change):
    x = np.ones((2, 2, 2))
    kw = {}
    if change == "subject":
        kw["subject"] = "unrelated"
    elif change == "space":
        kw["space"] = "MNI-template"
    elif change == "ontology":
        kw["ontology"] = {1: "different tissue"}
    else:
        kw["affine"] = np.diag([0.002, 0.001, 0.001, 1.0])
    with pytest.raises(ValueError):
        score(labels(x, **kw), labels(x))


def test_physical_surfel_distance_and_area_independent_translation():
    # One voxel is a rectangular 2×3×4-mm box: exact surface area 52 mm².
    x = np.ones((1, 1, 1))
    a = np.diag([0.002, 0.003, 0.004, 1.0])
    p, area = surfels(x, a)
    assert len(p) == 6
    assert_allclose(area.sum(), 52)
    # Opposite 2-mm face centers lie exactly 2 mm apart.
    assert_allclose(np.linalg.norm(p[0] - p[1]), 2)
    a = np.zeros((5, 5, 5), dtype=int)
    b = a.copy()
    a[1, 2, 2] = 1
    b[2, 2, 2] = 1
    row = score(labels(a), labels(b), tolerances_mm=(0.1, 1.0))["labels"][0]
    assert_allclose(row["Hausdorff_mm"], 1)
    assert row["boundaries"]["1.0"]["surface_Dice"] == 1
    assert row["boundaries"]["0.1"]["surface_Dice"] < 1


def test_declared_label_targets_include_missing_prediction():
    x = np.array([1, 2, 0, 0, 0, 0, 0, 0]).reshape(2, 2, 2)
    p = x.copy()
    p[p == 2] = 0
    ontology = {1: "first", 2: "second", 3: "absent"}
    result = score(labels(p, ontology=ontology), labels(x, ontology=ontology))
    assert result["macro_Dice"] == 0.5
    assert result["absent_both_labels"] == [3]


def test_explicit_nn_resampling_and_label_integrity():
    x = np.zeros((5, 5, 5), dtype=np.int16)
    x[2, 2, 2] = 7
    source = Volume(x, np.diag([0.001, 0.001, 0.001, 1.0]), "labels")
    reference = Volume(np.zeros((3, 3, 3)), np.diag([0.002, 0.002, 0.002, 1.0]))
    with pytest.raises(ValueError):
        resample(source, reference, order=1)
    result = resample(source, reference, order=0)
    assert set(np.unique(result.array())) == {0, 7}


def test_intensity_baseline_is_not_reference_labels():
    x = np.repeat(np.array([0.0, 10, 50, 100]), 27).reshape(3, 6, 6)
    image = Volume(x, np.diag([0.001, 0.001, 0.001, 1.0]))
    result = intensity_baseline(image)
    assert not result.metadata["truth_used"] and set(np.unique(result.array())) == {0, 1, 2, 3}
    with pytest.raises(ValueError):
        intensity_baseline(image, modality="T2")
