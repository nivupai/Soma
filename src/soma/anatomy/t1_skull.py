"""T1-only geometric baseline head surfaces: measured inner skull and scalp, offset outer skull.

This is an explicitly labelled baseline, not a skull segmentation. The inner skull comes from
the SynthSeg intracranial region (labels > 0, including extracerebral CSF 24), the scalp from a
T1 Otsu threshold, and the outer skull is the inner skull grown by a fixed physical offset: a
geometric prior, not a measurement. Readiness stays NOT_READY until the M33 skull protocol
(docs/MILESTONE33_SKULL_PROTOCOL.md) validates it against independent CT bone.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy import ndimage

from soma.anatomy.surfaces import ConductorSurfaces
from soma.geometry import Frame, Transform
from soma.imaging.mesh_quality import nested_boundaries
from soma.imaging.segmentation import process_mask, require_labels, threshold_mask
from soma.imaging.surfaces import Mesh, extract_surface, smooth
from soma.imaging.volumes import Volume
from soma.pipeline.synthseg import intracranial_mask, to_native_grid

METHOD = "T1-only geometric baseline; outer skull is an offset prior, not measured"
READINESS = "NOT_READY"
BOUNDARIES = ("inner_skull", "outer_skull", "outer_scalp")
# MNE BEM surface ids as required by ConductorSurfaces.from_mne:
# FIFFV_BEM_SURF_ID_BRAIN=1 (inner skull), _SKULL=3 (outer skull), _HEAD=4 (scalp).
MNE_SURFACE_IDS = {"inner_skull": 1, "outer_skull": 3, "outer_scalp": 4}


@dataclass(frozen=True)
class T1SkullParameters:
    """Every free choice of the baseline; recorded verbatim in provenance."""

    inner_closing_voxels: int = 2
    scalp_closing_voxels: int = 3
    scalp_threshold: float | None = None  # None: Otsu on the unpadded T1
    outer_offset_mm: float = 6.0
    scalp_margin_mm: float = 2.0  # outer skull stays at least this far inside the scalp
    minimum_gap_mm: float = 1.0  # inner skull stays at least this far inside the outer skull
    padding_voxels: int = 4
    smoothing_iterations: int = 10
    smoothing_step: float = 0.1
    minimum_separation_m: float = 0.0005

    def __post_init__(self) -> None:
        if min(self.inner_closing_voxels, self.scalp_closing_voxels, self.padding_voxels) < 0:
            raise ValueError("Morphology iterations and padding must be nonnegative")
        if not self.outer_offset_mm > 0 or self.scalp_margin_mm < 0 or self.minimum_gap_mm < 0:
            raise ValueError("Positive outer offset and nonnegative margins required")
        if self.padding_voxels <= max(self.inner_closing_voxels, self.scalp_closing_voxels):
            raise ValueError("Padding must exceed the closing radius so masks never touch edges")


def pad(volume: Volume, voxels: int) -> Volume:
    """Zero-pad a volume symmetrically; the affine keeps every voxel at its physical place."""
    if voxels < 0:
        raise ValueError("Padding must be nonnegative")
    if voxels == 0:
        return volume
    shift = np.eye(4)
    shift[:3, 3] = -voxels
    return Volume(
        np.pad(volume.array(), voxels),
        volume.affine_m @ shift,
        volume.kind,
        {**volume.metadata, "padding_voxels": voxels},
    )


def depth_mm(mask: np.ndarray[Any, Any], spacing_m: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Approximate physical depth (mm) of each voxel centre inside ``mask`` below its boundary.

    The Euclidean distance to the nearest outside voxel centre, minus half a voxel, since the
    extracted (marching-cubes 0.5) boundary lies halfway between inside and outside centres.
    """
    spacing_mm = spacing_m * 1000
    edt = np.asarray(ndimage.distance_transform_edt(mask, sampling=spacing_mm))
    return np.where(mask, edt - 0.5 * float(spacing_mm.min()), 0.0)


def mask_volume(data: np.ndarray[Any, Any], like: Volume, **metadata: Any) -> Volume:
    return Volume(data.astype(np.uint8), like.affine_m, "labels", dict(metadata))


def boundary_mesh(mask: Volume, *, iterations: int, step: float) -> Mesh:
    """Largest-component marching-cubes boundary of a binary mask, then bounded smoothing."""
    largest = process_mask(mask, largest_component=True)
    mesh = extract_surface(largest)
    return smooth(mesh, iterations=iterations, step=step) if iterations else mesh


def vertex_normals(mesh: Mesh) -> np.ndarray[Any, Any]:
    """Area-weighted outward vertex normals (meshes here are wound outward)."""
    xyz = mesh.vertices.xyz
    tri = xyz[mesh.faces]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals = np.zeros_like(xyz)
    for i in range(3):
        np.add.at(normals, mesh.faces[:, i], face)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return np.asarray(normals / np.maximum(length, 1e-30))


@dataclass(frozen=True)
class T1SkullEstimate:
    masks: dict[str, Volume]
    meshes: dict[str, Mesh]
    provenance: dict[str, Any]
    nesting: dict[str, Any] | None = None
    ras_to_mri: Transform = field(
        default_factory=lambda: Transform(Frame.RAS, Frame.MRI, np.eye(4))
    )

    def mne_surfaces(self) -> list[dict[str, Any]]:
        """MNE-style BEM surface records (metres, coord_frame 5 = MRI), inner to outer."""
        records = []
        for name in BOUNDARIES:
            mesh = self.meshes[name]
            rr = self.ras_to_mri.apply(mesh.vertices).xyz
            records.append(
                {
                    "id": MNE_SURFACE_IDS[name],
                    "rr": rr,
                    "tris": np.array(mesh.faces),
                    "coord_frame": 5,
                    "np": len(rr),
                    "ntri": len(mesh.faces),
                }
            )
        return records

    def conductor(self, subject: str) -> ConductorSurfaces:
        return ConductorSurfaces.from_mne(subject, self.mne_surfaces(), self.provenance)


def estimate_t1_skull(
    t1: Volume,
    synthseg_labels: Volume,
    *,
    parameters: T1SkullParameters | None = None,
    check_nesting: bool = True,
    ras_to_mri: Transform | None = None,
) -> T1SkullEstimate:
    """Build the three baseline boundaries on a padded copy of the T1 grid."""
    p = parameters or T1SkullParameters()
    if t1.kind != "intensity":
        raise ValueError("T1 intensity volume required")
    require_labels(synthseg_labels)
    labels, grid_receipt = to_native_grid(synthseg_labels, t1)
    n = p.padding_voxels
    padded_t1 = pad(t1, n)
    spacing = padded_t1.spacing_m

    inner = process_mask(
        pad(intracranial_mask(labels, dilation_voxels=0), n),
        closing_iterations=p.inner_closing_voxels,
        fill_holes=True,
        largest_component=True,
    )
    threshold = threshold_mask(t1, threshold=p.scalp_threshold)
    scalp = process_mask(
        pad(threshold, n),
        closing_iterations=p.scalp_closing_voxels,
        fill_holes=True,
        largest_component=True,
    )
    inner_mask, scalp_mask = inner.array().astype(bool), scalp.array().astype(bool)
    if not inner_mask.any() or not scalp_mask.any():
        raise ValueError("Empty intracranial or scalp mask")

    grown = depth_mm(~inner_mask, spacing) <= p.outer_offset_mm
    allowed = depth_mm(scalp_mask, spacing) >= p.scalp_margin_mm
    outer_mask = np.asarray(ndimage.binary_fill_holes(grown & allowed))
    labelled, count = ndimage.label(outer_mask)
    if count > 1:
        outer_mask = labelled == np.argmax(np.bincount(labelled.ravel())[1:]) + 1
    kept_inner = inner_mask & (depth_mm(outer_mask, spacing) >= p.minimum_gap_mm)
    labelled, count = ndimage.label(kept_inner)
    if count > 1:
        kept_inner = labelled == np.argmax(np.bincount(labelled.ravel())[1:]) + 1
    if not kept_inner.any():
        raise ValueError("Inner skull vanished after scalp clipping")

    common = {"method": METHOD, "subject_grid": t1.grid_id}
    masks = {
        "inner_skull": mask_volume(kept_inner, padded_t1, boundary="inner_skull", **common),
        "outer_skull": mask_volume(outer_mask, padded_t1, boundary="outer_skull", **common),
        "outer_scalp": mask_volume(scalp_mask, padded_t1, boundary="outer_scalp", **common),
    }
    meshes = {
        name: boundary_mesh(masks[name], iterations=p.smoothing_iterations, step=p.smoothing_step)
        for name in BOUNDARIES
    }
    nesting = (
        nested_boundaries(
            [meshes[b] for b in BOUNDARIES], minimum_separation_m=p.minimum_separation_m
        )
        if check_nesting
        else None
    )
    transform = ras_to_mri or Transform(Frame.RAS, Frame.MRI, np.eye(4))
    voxel_mm3 = float(np.prod(spacing * 1000))
    provenance: dict[str, Any] = {
        "method": METHOD,
        "readiness": READINESS,
        "readiness_reason": "not validated against independent CT bone (M33 skull protocol)",
        "parameters": asdict(p),
        "outer_skull_measured": False,
        "inputs": {
            "t1_sha256": t1.metadata.get("source_sha256"),
            "synthseg_sha256": synthseg_labels.metadata.get("source_sha256"),
            "t1_grid": t1.geometry(),
            "synthseg_native_grid_return": grid_receipt,
            "synthseg_labels": "all labels > 0, including extracerebral CSF (24)",
        },
        "scalp_threshold": threshold.metadata["segmentation"]["threshold"],
        "scalp_threshold_rule": "explicit" if p.scalp_threshold is not None else "Otsu",
        "clipping": {
            "outer_voxels_removed_by_scalp_margin": int(np.sum(grown & ~allowed)),
            "inner_voxels_removed_by_gap": int(np.sum(inner_mask & ~kept_inner)),
        },
        "volumes_mm3": {name: float(masks[name].array().sum() * voxel_mm3) for name in BOUNDARIES},
        "mne_surface_ids": MNE_SURFACE_IDS,
        "ras_to_mri": {
            "matrix": transform.matrix.tolist(),
            "identity_default": ras_to_mri is None,
            "note": (
                "identity means NIfTI scanner RAS is used as the MNE MRI frame; supply the "
                "FreeSurfer surface-RAS transform before combining with sensor coregistration"
            ),
        },
        "nesting_checked": check_nesting,
        "geometric_candidate": None if nesting is None else bool(nesting["geometric_candidate"]),
        "anatomical_truth_claim": False,
        "clinical_certification": False,
    }
    return T1SkullEstimate(masks, meshes, provenance, nesting, transform)


__all__ = [
    "BOUNDARIES",
    "METHOD",
    "MNE_SURFACE_IDS",
    "READINESS",
    "T1SkullEstimate",
    "T1SkullParameters",
    "boundary_mesh",
    "depth_mm",
    "estimate_t1_skull",
    "pad",
    "vertex_normals",
]
