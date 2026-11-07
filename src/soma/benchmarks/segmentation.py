"""Subject/ontology-aware overlap and physical surfel segmentation metrics."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.spatial import cKDTree
from skimage.filters import threshold_multiotsu

from soma.imaging.segmentation import require_labels
from soma.imaging.volumes import Volume


@dataclass(frozen=True)
class LabelVolume:
    volume: Volume
    subject: str
    space: str
    ontology: dict[int, str]
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        require_labels(self.volume)
        if not self.subject or not self.space or not self.ontology or not self.provenance:
            raise ValueError(
                "Subject, world-space identity, target label ontology and provenance required"
            )
        if any(not isinstance(k, int) or k <= 0 or not v for k, v in self.ontology.items()):
            raise ValueError(
                "Positive target IDs with unambiguous anatomical interpretation required"
            )


def corresponding(prediction: LabelVolume, reference: LabelVolume) -> None:
    if prediction.subject != reference.subject or prediction.space != reference.space:
        raise ValueError("Subject/world-space mismatch; scoring never registers inputs")
    if prediction.ontology != reference.ontology:
        raise ValueError("Label interpretation mismatch")
    if not prediction.volume.same_grid(reference.volume):
        raise ValueError(
            "Voxel-grid mismatch; explicit justified nearest-neighbor resampling required"
        )


def surfels(mask: Any, affine_m: Any) -> tuple[Any, Any]:
    """Exposed voxel-face centers and physical parallelogram areas (mm, mm²)."""
    x = np.asarray(mask, dtype=bool)
    a = np.asarray(affine_m, dtype=float)
    points = []
    areas = []
    for axis in range(3):
        other = [j for j in range(3) if j != axis]
        area = float(np.linalg.norm(np.cross(a[:3, other[0]], a[:3, other[1]])) * 1e6)
        for direction in (-1, 1):
            neighbor = np.roll(x, -direction, axis=axis)
            edge: list[Any] = [slice(None)] * 3
            edge[axis] = -1 if direction == 1 else 0
            neighbor[tuple(edge)] = False
            indices = np.argwhere(x & ~neighbor).astype(float)
            indices[:, axis] += direction * 0.5
            points.append((indices @ a[:3, :3].T + a[:3, 3]) * 1000)
            areas.append(np.full(len(indices), area))
    return np.concatenate(points), np.concatenate(areas)


def _quantile(values: Any, weights: Any, p: float) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    index = np.searchsorted(cumulative, p * cumulative[-1])
    return float(values[order[min(index, len(order) - 1)]])


def score(
    prediction: LabelVolume,
    reference: LabelVolume,
    *,
    tolerances_mm: tuple[float, ...] = (1.0, 2.0),
) -> dict[str, Any]:
    corresponding(prediction, reference)
    if not tolerances_mm or any(not np.isfinite(x) or x <= 0 for x in tolerances_mm):
        raise ValueError("Positive finite physical tolerances required")
    a, b = require_labels(prediction.volume), require_labels(reference.volume)
    voxel_mm3 = abs(float(np.linalg.det(reference.volume.affine_m[:3, :3]))) * 1e9
    rows: list[dict[str, Any]] = []
    for label, name in reference.ontology.items():
        p, r = a == label, b == label
        npred, nref = int(p.sum()), int(r.sum())
        tp = int(np.count_nonzero(p & r))
        fp = npred - tp
        fn = nref - tp
        tn = p.size - tp - fp - fn
        both = npred + nref
        row: dict[str, Any] = {
            "label": label,
            "name": name,
            "case": "absent_both"
            if both == 0
            else "reference_absent"
            if nref == 0
            else "prediction_absent"
            if npred == 0
            else "present",
            "Dice": 2 * tp / both if both else None,
            "Jaccard": tp / (tp + fp + fn) if tp + fp + fn else None,
            "sensitivity": tp / nref if nref else None,
            "specificity": tn / (tn + fp) if tn + fp else None,
            "reference_volume_mm3": nref * voxel_mm3,
            "prediction_volume_mm3": npred * voxel_mm3,
            "absolute_volume_error_mm3": abs(npred - nref) * voxel_mm3,
            "relative_volume_error": abs(npred - nref) / nref if nref else None,
            "signed_relative_volume_error": (npred - nref) / nref if nref else None,
            "ASSD_mm": None,
            "Hausdorff_mm": None,
            "HD95_mm": None,
            "boundaries": {},
        }
        if npred and nref:
            pp, ap = surfels(p, prediction.volume.affine_m)
            rr, ar = surfels(r, reference.volume.affine_m)
            dp = cKDTree(rr).query(pp)[0]
            dr = cKDTree(pp).query(rr)[0]
            distances = np.r_[dp, dr]
            weights = np.r_[ap, ar]
            row.update(
                {
                    "ASSD_mm": float(np.sum(distances * weights) / weights.sum()),
                    "Hausdorff_mm": float(distances.max()),
                    "HD95_mm": _quantile(distances, weights, 0.95),
                    "prediction_surface_area_mm2": float(ap.sum()),
                    "reference_surface_area_mm2": float(ar.sum()),
                }
            )
            for tolerance in tolerances_mm:
                pm = float(ap[dp <= tolerance].sum())
                rm = float(ar[dr <= tolerance].sum())
                row["boundaries"][str(tolerance)] = {
                    "surface_Dice": (pm + rm) / float(ap.sum() + ar.sum()),
                    "precision": pm / float(ap.sum()),
                    "recall": rm / float(ar.sum()),
                }
        else:
            for tolerance in tolerances_mm:
                row["boundaries"][str(tolerance)] = {
                    "surface_Dice": 0.0 if both else None,
                    "precision": 0.0 if npred else None,
                    "recall": 0.0 if nref else None,
                }
        rows.append(row)
    dice = [x["Dice"] for x in rows if x["Dice"] is not None]
    return {
        "subject": reference.subject,
        "prediction_geometry": prediction.volume.geometry(),
        "reference_geometry": reference.volume.geometry(),
        "space": reference.space,
        "labels": rows,
        "macro_Dice": float(np.mean(dice)) if dice else None,
        "absent_both_labels": [x["label"] for x in rows if x["case"] == "absent_both"],
        "boundary_definition": (
            "area-weighted exposed voxel-face centers in physical mm; finite "
            "voxel representation, not exact continuous tissue boundary"
        ),
        "HD95_definition": "pooled physical-surface-area weighted empirical 95th percentile",
        "registration_performed": False,
        "automatic_resampling": False,
        "prediction_provenance": prediction.provenance,
        "reference_provenance": reference.provenance,
    }


def intensity_baseline(image: Volume, *, modality: str = "T1") -> Volume:
    data = image.array(dtype=np.float32)
    if (
        modality != "T1"
        or image.kind != "intensity"
        or not np.isfinite(data).all()
        or data.max() <= 0
    ):
        raise ValueError("Finite positive-range T1 intensity phantom required")
    foreground = data > float(data.max()) * 0.02
    if len(np.unique(data[foreground])) < 3:
        raise ValueError("Insufficient T1 histogram classes")
    counts, edges = np.histogram(data[foreground], bins=256)
    centers = (edges[:-1] + edges[1:]) / 2
    split_centers = threshold_multiotsu(hist=(counts, centers), classes=3)
    split_indices = np.searchsorted(centers, split_centers)
    thresholds = edges[split_indices + 1]
    labels = np.zeros(data.shape, dtype=np.uint8)
    labels[foreground] = np.digitize(data[foreground], thresholds) + 1
    return Volume(
        labels,
        image.affine_m,
        "labels",
        {
            "subject": image.metadata.get("subject"),
            "space": image.metadata.get("space"),
            "method": "T1 three-class global multi-Otsu foreground>2%max, low/mid/high→CSF/GM/WM",
            "thresholds": thresholds.tolist(),
            "multiotsu_histogram_split_centers": split_centers.tolist(),
            "histogram_bins": 256,
            "application_policy": (
                "upper histogram-bin edges preserve the fitted histogram partition"
            ),
            "truth_used": False,
            "extracranial_voxels_excluded": False,
        },
    )
