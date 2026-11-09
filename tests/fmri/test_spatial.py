"""Independent coordinate, interpolation, ROI and cross-modal identity oracles."""

from dataclasses import replace

import numpy as np
import pytest

from soma.fmri.spatial import (
    SpatialChain,
    SpatialMap,
    aggregate_sources,
    align_roi,
    compare_regions,
    project_points,
    roi_estimates,
    sample_points,
)
from soma.geometry import Frame, Points, Transform
from soma.imaging.volumes import Volume


@pytest.fixture
def image():
    xyz = np.indices((5, 5, 5))
    field = xyz[0] + 2 * xyz[1] + 3 * xyz[2]
    affine = np.diag([0.002, 0.003, 0.004, 1.0])
    affine[:3, 3] = [-0.004, -0.006, -0.008]
    return SpatialMap(
        Volume(field, affine),
        "s",
        "native",
        "linear field",
        {"source": "analytic", "midline_RAS_x0_validated": True},
    )


@pytest.fixture
def roi(image):
    labels = np.zeros((5, 5, 5), np.uint8)
    labels[:2] = 1
    labels[3:] = 2
    return SpatialMap(
        Volume(labels, image.volume.affine_m, "labels"),
        "s",
        "native",
        "ROI",
        {"source": "analytic atlas", "label_mapping": {"1": "left", "2": "right", "3": "absent"}},
    )


def test_trilinear_independent_world_oracle(image):
    voxel = np.array([[0.25, 1.5, 2.25], [2.5, 2.1, 3.5]])
    xyz = voxel * np.array([0.002, 0.003, 0.004]) + np.array([-0.004, -0.006, -0.008])
    points = Points(xyz, Frame.RAS)
    expected = voxel[:, 0] + 2 * voxel[:, 1] + 3 * voxel[:, 2]
    np.testing.assert_allclose(
        sample_points(image, points, subject="s", space="native"), expected, atol=1e-12
    )
    np.testing.assert_allclose(image.volume.grid.to_voxel(points), voxel, atol=1e-12)


def test_sparse_surface_projection_and_coverage(image, roi):
    indices = np.array([[1.0, 2.0, 2.0], [1.0, 2.0, 2.0], [3.0, 2.0, 2.0]])
    points = image.volume.grid.to_world(indices)
    output, count = project_points(
        image, points, np.array([2.0, 4.0, 9.0]), subject="s", space="native"
    )
    assert output.array()[1, 2, 2] == 3 and count.array()[1, 2, 2] == 2
    assert count.array()[0, 0, 0] == 0
    stats = aggregate_sources(roi, points, np.array([2.0, 4.0, 9.0]), subject="s", space="native")
    assert stats["1"]["mean"] == 3 and stats["2"]["mean"] == 9 and stats["3"]["mean"] is None


def test_ROI_effect_physical_volume_and_absence(image, roi):
    rows = roi_estimates(image, roi)
    assert rows[0]["mean_effect"] == pytest.approx(image.volume.array()[:2].mean())
    assert rows[0]["volume_mm3"] == pytest.approx(50 * 24)
    assert rows[2]["coverage"] == "absent"
    assert rows[0]["inferential_ROI_standard_error"].startswith("unavailable")


@pytest.mark.parametrize(
    "fault", ["subject", "space", "frame", "coverage", "hemisphere", "unvalidated-midline"]
)
def test_sampling_safeguards(image, fault):
    points = Points(np.array([[-0.002, 0.0, 0.0]]), Frame.RAS)
    with pytest.raises(ValueError):
        if fault == "subject":
            sample_points(image, points, subject="other", space="native")
        elif fault == "space":
            sample_points(image, points, subject="s", space="MNI")
        elif fault == "frame":
            sample_points(image, Points(points.xyz, Frame.LPS), subject="s", space="native")
        elif fault == "coverage":
            sample_points(
                image, Points(np.array([[0.2, 0, 0]]), Frame.RAS), subject="s", space="native"
            )
        elif fault == "hemisphere":
            sample_points(image, points, subject="s", space="native", hemisphere="right")
        else:
            sample_points(
                replace(image, provenance={"source": "test"}),
                points,
                subject="s",
                space="native",
                hemisphere="left",
            )


def test_roi_transform_direction_and_nearest_labels(image, roi):
    other = replace(roi, space="atlas")
    with pytest.raises(ValueError, match="chain"):
        align_roi(other, image)
    chain = SpatialChain(
        "s", "native", "atlas", Transform(Frame.RAS, Frame.RAS, np.eye(4)), "analytic transform"
    )
    result = align_roi(other, image, chain)
    np.testing.assert_array_equal(result.volume.array(), roi.volume.array())
    with pytest.raises(ValueError, match="direction"):
        align_roi(other, image, replace(chain, reference_space="atlas", source_space="native"))
    with pytest.raises(ValueError):
        align_roi(replace(roi, subject="other"), image)
    matrix = np.eye(4)
    matrix[0, 3] = 0.002
    shifted = align_roi(
        other, image, replace(chain, reference_to_source=Transform(Frame.RAS, Frame.RAS, matrix))
    )
    assert shifted.volume.array()[1, 2, 2] == 0  # reference voxel1 maps source voxel2
    assert set(np.unique(shifted.volume.array())) == {0, 1, 2}


def regional(subject="s", dataset="d"):
    return {
        "subject": subject,
        "dataset": dataset,
        "release": "v1",
        "task": "motor",
        "visit": "A",
        "modality": "EEG",
        "task_mapping": "explicit motor task comparison",
        "quantity": "EEG power",
        "roi_ontology": "explicit-v1",
        "values": {"a": 1.0, "b": 3.0, "c": 2.0},
        "spatial_evidence": "analytic",
        "visit_mapping": "MRI-A EEG-B",
    }


def test_cross_dataset_is_descriptive_and_matched_mode_guard():
    a, b = regional(), regional("other", "other-dataset")
    b["modality"] = "fMRI"
    result = compare_regions(a, b, mode="cross-dataset")
    assert result["descriptive_correlation"] == pytest.approx(1)
    assert result["physiological_equivalence_claimed"] is False
    assert result["simultaneous_assumed"] is False
    with pytest.raises(ValueError, match="same subject"):
        compare_regions(a, b, mode="participant-matched")
    b = regional()
    b["modality"] = "fMRI"
    b["quantity"] = "BOLD"
    b["visit"] = "B"
    assert compare_regions(a, b, mode="participant-matched")["population_inference"] is False


@pytest.mark.parametrize(
    "fault", ["ontology", "regions", "mapping", "provenance", "constant", "release"]
)
def test_multimodal_adversarial(fault):
    a, b = regional(), regional()
    b["modality"] = "fMRI"
    if fault == "ontology":
        b["roi_ontology"] = "other"
    elif fault == "regions":
        b["values"] = {"x": 1, "y": 2}
    elif fault == "mapping":
        b["visit_mapping"] = "wrong"
    elif fault == "provenance":
        b["spatial_evidence"] = ""
    elif fault == "constant":
        b["values"] = {"a": 1, "b": 1, "c": 1}
    else:
        b["release"] = "v2"
    with pytest.raises(ValueError):
        compare_regions(a, b, mode="participant-matched")
