"""Guarded ROI/surface interfaces reuse Soma physical coordinates and resampling."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.ndimage import map_coordinates

from soma.geometry import Frame, Points, Transform
from soma.imaging.resampling import resample
from soma.imaging.volumes import Volume


@dataclass(frozen=True)
class SpatialMap:
    volume: Volume
    subject: str
    space: str
    quantity: str
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        if not all([self.subject, self.space, self.quantity]) or not self.provenance.get("source"):
            raise ValueError("Spatial map requires subject, space, quantity and source")


@dataclass(frozen=True)
class SpatialChain:
    subject: str
    reference_space: str
    source_space: str
    reference_to_source: Transform
    evidence: str

    def __post_init__(self) -> None:
        if (
            not self.evidence
            or not self.subject
            or not self.reference_space
            or not self.source_space
        ):
            raise ValueError("Identified transform chain and evidence required")
        if (
            not isinstance(self.reference_to_source, Transform)
            or self.reference_to_source.source != Frame.RAS
            or self.reference_to_source.destination != Frame.RAS
        ):
            raise ValueError(
                "Spatial chain must explicitly map reference RAS metres to source RAS metres"
            )


def align_roi(roi: SpatialMap, target: SpatialMap, chain: SpatialChain | None = None) -> SpatialMap:
    if roi.subject != target.subject:
        raise ValueError("ROI and image subjects differ")
    if roi.volume.kind != "labels" or not roi.provenance.get("label_mapping"):
        raise ValueError("Discrete ROI requires explicit label mapping/atlas metadata")
    if chain is None:
        if roi.space != target.space or not roi.volume.same_grid(target.volume):
            raise ValueError("Different spaces/grids require a validated reference-to-source chain")
        return roi
    if (chain.subject, chain.reference_space, chain.source_space) != (
        target.subject,
        target.space,
        roi.space,
    ):
        raise ValueError("Transform subject/space/direction mismatch")
    result = resample(
        roi.volume, target.volume, reference_to_source=chain.reference_to_source, order=0
    )
    return SpatialMap(
        result,
        roi.subject,
        target.space,
        roi.quantity,
        {
            **roi.provenance,
            "transform_evidence": chain.evidence,
            "interpolation": "nearest",
            "partial_volume_warning": True,
        },
    )


def roi_estimates(effect: SpatialMap, roi: SpatialMap) -> list[dict[str, Any]]:
    aligned = align_roi(roi, effect)
    labels = aligned.volume.array()
    mapping = {int(k): v for k, v in roi.provenance["label_mapping"].items()}
    if not set(np.unique(labels)).issubset({0, *mapping}):
        raise ValueError("Unknown ROI label ontology")
    rows = []
    for label, name in mapping.items():
        selected = labels == label
        values = effect.volume.array()[selected]
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite ROI effects")
        rows.append(
            {
                "label": label,
                "name": name,
                "n_voxels": int(selected.sum()),
                "volume_mm3": float(
                    selected.sum() * abs(np.linalg.det(effect.volume.affine_m[:3, :3])) * 1e9
                ),
                "mean_effect": float(values.mean()) if values.size else None,
                "coverage": "present" if values.size else "absent",
                "partial_volume_warning": True,
                "inferential_ROI_standard_error": "unavailable: spatial covariance not modeled",
            }
        )
    return rows


def sample_points(
    image: SpatialMap, points: Points, *, subject: str, space: str, hemisphere: str | None = None
) -> np.ndarray[Any, Any]:
    if subject != image.subject or space != image.space:
        raise ValueError("Point/source subject or anatomical space mismatch")
    if points.frame != Frame.RAS:
        raise ValueError("Volume sampling needs RAS metres")
    if hemisphere is not None:
        if image.provenance.get("midline_RAS_x0_validated") is not True:
            raise ValueError("Hemisphere test requires validated midsagittal reference")
        if hemisphere not in {"left", "right"} or np.any(
            points.xyz[:, 0] * (-1 if hemisphere == "left" else 1) < 0
        ):
            raise ValueError("Incorrect hemisphere/axis flip")
    voxel = image.volume.grid.to_voxel(points)
    if np.any(voxel < 0) or np.any(voxel > np.array(image.volume.shape) - 1):
        raise ValueError("Surface/points fall outside image coverage; check units and transforms")
    values = np.asarray(
        map_coordinates(image.volume.array().astype(float), voxel.T, order=1, mode="nearest")
    )
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite sampled image values")
    return values


def project_points(
    reference: SpatialMap, points: Points, values: np.ndarray[Any, Any], *, subject: str, space: str
) -> tuple[Volume, Volume]:
    sample_points(reference, points, subject=subject, space=space)
    if values.shape != (len(points.xyz),) or not np.isfinite(values).all():
        raise ValueError("Finite source values must align to point identities")
    indices = np.rint(reference.volume.grid.to_voxel(points)).astype(int)
    sums = np.zeros(reference.volume.shape)
    counts = np.zeros(reference.volume.shape, dtype=np.int32)
    np.add.at(sums, tuple(indices.T), values)
    np.add.at(counts, tuple(indices.T), 1)
    output = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    return Volume(output, reference.volume.affine_m), Volume(
        counts, reference.volume.affine_m, "labels"
    )


def aggregate_sources(
    roi: SpatialMap, points: Points, values: np.ndarray[Any, Any], *, subject: str, space: str
) -> dict[str, Any]:
    sample_points(roi, points, subject=subject, space=space)
    if values.shape != (len(points.xyz),) or not np.isfinite(values).all():
        raise ValueError("Source values do not match source coordinates")
    indices = np.rint(roi.volume.grid.to_voxel(points)).astype(int)
    labels = roi.volume.array()[tuple(indices.T)]
    return {
        str(code): {
            "n_sources": int(np.sum(labels == int(code))),
            "mean": float(np.mean(values[labels == int(code)]))
            if np.any(labels == int(code))
            else None,
        }
        for code in roi.provenance.get("label_mapping", {})
    }


def compare_regions(left: dict[str, Any], right: dict[str, Any], *, mode: str) -> dict[str, Any]:
    required = {
        "modality",
        "subject",
        "dataset",
        "release",
        "task",
        "visit",
        "quantity",
        "roi_ontology",
        "values",
        "spatial_evidence",
    }
    if any(not required.issubset(x) or not x["spatial_evidence"] for x in [left, right]):
        raise ValueError("Regional comparison requires explicit modality/visit/space provenance")
    if {left["modality"], right["modality"]} != {"EEG", "fMRI"}:
        raise ValueError("Explicit EEG and fMRI modality provenance required")
    if left["roi_ontology"] != right["roi_ontology"] or set(left["values"]) != set(right["values"]):
        raise ValueError("ROI definitions differ")
    if mode not in {"cross-dataset", "participant-matched"}:
        raise ValueError("Unknown multimodal comparison mode")
    if mode == "participant-matched":
        if any(left[k] != right[k] for k in ["subject", "dataset", "release"]):
            raise ValueError(
                "Participant-matched comparison requires same subject within dataset release"
            )
        if not left.get("task_mapping") or left["task_mapping"] != right.get("task_mapping"):
            raise ValueError("Explicit shared task mapping required")
        if not left.get("visit_mapping") or left["visit_mapping"] != right.get("visit_mapping"):
            raise ValueError(
                "Explicit shared visit/task mapping required; no simultaneity assumption"
            )
    names = sorted(left["values"])
    x, y = [np.array([record["values"][n] for n in names], float) for record in [left, right]]
    if len(x) < 2 or not np.isfinite([x, y]).all() or np.std(x) == 0 or np.std(y) == 0:
        raise ValueError("At least two finite varying regional values required")
    return {
        "mode": mode,
        "regions": names,
        "descriptive_correlation": float(np.corrcoef(x, y)[0, 1]),
        "left": left,
        "right": right,
        "simultaneous_assumed": False,
        "physiological_equivalence_claimed": False,
        "population_inference": False,
        "unidentified": ["registration error", "source leakage", "physiological differences"],
    }
