"""Explicit evidence categories and bounded surface/derivative-volume checks."""

from dataclasses import dataclass
from typing import Any, Literal

import nibabel as nib
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from soma.anatomy.surfaces import distance_to_surface
from soma.core.provenance import sha256
from soma.geometry import Frame
from soma.geometry.coordinates import validate_affine
from soma.imaging.mesh_quality import contains

Category = Literal[
    "computationally_verified",
    "external_reference",
    "heuristically_assessed",
    "not_assessed",
    "failed",
]


@dataclass(frozen=True)
class Evidence:
    property: str
    category: Category
    status: str
    definition: str
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        allowed = {
            "computationally_verified": {"PASS"},
            "external_reference": {"PASS"},
            "heuristically_assessed": {"INDETERMINATE"},
            "not_assessed": {"INDETERMINATE"},
            "failed": {"FAIL"},
        }
        if (
            self.category not in allowed
            or self.status not in allowed[self.category]
            or not self.definition
            or not self.provenance
        ):
            raise ValueError("Evidence requires explicit supported category/check/provenance")

    def to_dict(self) -> dict[str, Any]:
        # JSON supports MNE list subclasses; dataclasses.asdict reconstructs them
        # with an unsupported constructor and must not be used for provenance.
        return {
            "property": self.property,
            "category": self.category,
            "status": self.status,
            "definition": self.definition,
            "provenance": self.provenance,
        }


def evidence_state(records: list[Evidence]) -> str:
    if not records:
        return "INDETERMINATE"
    return (
        "FAIL"
        if any(x.status == "FAIL" for x in records)
        else "INDETERMINATE"
        if any(x.status == "INDETERMINATE" for x in records)
        else "PASS"
    )


def surface_mask_consistency(
    mesh: Any, mask: Any, voxel_to_MRI_m: Any, *, limit: int = 20000
) -> dict[str, Any]:
    if mesh.vertices.frame != Frame.MRI:
        raise ValueError("Surface-mask audit requires explicit MRI surface coordinates")
    a = validate_affine(voxel_to_MRI_m)
    data = np.asarray(mask)
    if (
        data.ndim != 3
        or data.dtype.kind not in "biu"
        or not set(np.unique(data)) <= {0, 1}
        or not data.any()
        or data.all()
        or limit < 1
    ):
        raise ValueError("Nonempty bounded binary reference mask required")
    binary = data.astype(bool)
    boundary = binary & ~ndimage.binary_erosion(binary)
    indices = np.argwhere(boundary)
    xyz = indices @ a[:3, :3].T + a[:3, 3]
    distance = cKDTree(xyz).query(mesh.vertices.xyz)[0]
    ijk = np.linalg.solve(a[:3, :3], (mesh.vertices.xyz - a[:3, 3]).T)
    in_mask = (
        ndimage.map_coordinates(binary.astype(np.uint8), ijk, order=0, mode="constant", cval=0) > 0
    )
    flat = np.flatnonzero(binary)
    selected = flat[np.linspace(0, len(flat) - 1, min(limit, len(flat)), dtype=int)]
    coords = np.column_stack(np.unravel_index(selected, data.shape))
    points = coords @ a[:3, :3].T + a[:3, 3]
    enclosed = contains(mesh, points)
    _, components = ndimage.label(binary)
    return {
        "surface_to_boundary_voxel_center_distance_m": distance.tolist(),
        "signed_surface_distance_m": np.where(in_mask, -distance, distance).tolist(),
        "surface_vertices_inside_mask_fraction": float(in_mask.mean()),
        "sampled_mask_centers_inside_surface_fraction": float(enclosed.mean()),
        "mask_sample_count": len(points),
        "mask_components_6_connected": int(components),
        "voxel_to_MRI_m": a.tolist(),
        "voxel_center_discretization_bound_m": float(np.linalg.norm(a[:3, :3], axis=0).sum() / 2),
        "distance_definition": (
            "nearest foreground boundary voxel center; not exact continuous tissue boundary"
        ),
        "sampling": (
            "deterministic equal-spaced foreground flat indices; descriptive, no binomial interval"
        ),
        "Dice": None,
        "independent_anatomical_ground_truth": False,
    }


def assess_anatomy(assets: Any, model: Any, prepared: dict[str, Any], limit: int) -> dict[str, Any]:
    readiness = prepared["readiness"]
    records = []

    def add(
        name: str, category: Category, status: str, definition: str, provenance: dict[str, Any]
    ) -> None:
        records.append(Evidence(name, category, status, definition, provenance))

    add(
        "MRI_provenance",
        "external_reference",
        "PASS",
        "Curated sample paths and selected asset hashes agree; not authenticated clinical identity",
        prepared["identity"],
    )
    add(
        "surface_generation",
        "external_reference",
        "PASS",
        "Distributed participant FLASH surfaces; generation independently unvalidated",
        model.surfaces.provenance,
    )
    for name in (
        "topology",
        "geometry",
        "coordinate_consistency",
        "sensor_compatibility",
        "numerical_mesh_quality",
    ):
        check = readiness["checks"][name]["status"]
        add(
            name,
            "computationally_verified"
            if check == "PASS"
            else "failed"
            if check == "FAIL"
            else "not_assessed",
            check,
            "M8 scoped ico3 solver checks and stated tolerances; not anatomical truth",
            {"readiness": name, "minimum_gap_m": readiness["minimum_separation_m"]},
        )
    for name, passed, definition in [
        (
            "surface_nesting",
            readiness["nesting"]["geometric_candidate"],
            "Solid-angle containment, no crossing and minimum 0.1-mm separation",
        ),
        (
            "self_intersections",
            all(
                q["self_intersection_check"]["intersecting_or_touching_triangle_pairs"] == 0
                for q in readiness["quality"]
            ),
            "Nonadjacent triangle intersections at tolerance 1e-8 m",
        ),
        (
            "mesh_orientation",
            all(
                q["outward_global_winding"] and q["inconsistent_oriented_edges"] == 0
                for q in readiness["quality"]
            ),
            "Positive global signed volume and consistently oriented adjacent faces",
        ),
    ]:
        add(
            name,
            "computationally_verified" if passed else "failed",
            "PASS" if passed else "FAIL",
            definition,
            {"solver_mesh": "ico3", "anatomical_truth": False},
        )
    add(
        "transform_chain",
        "computationally_verified",
        "PASS",
        "Explicit rigid HEAD→MRI and stored MGH voxel→surface-RAS; source/sensor identity checked",
        model.receipt(),
    )
    derivatives = {}
    for name, surface in [
        ("brainmask.mgz", model.surfaces.meshes[0]),
        ("seghead.mgz", model.surfaces.meshes[2]),
    ]:
        path = assets.subject_dir / "mri" / name
        if not path.exists():
            add(
                name,
                "not_assessed",
                "INDETERMINATE",
                "Reference derivative absent",
                {"expected_path": str(path)},
            )
            continue
        image: Any = nib.load(path)
        affine = np.asarray(image.header.get_vox2ras_tkr(), dtype=float)
        affine[:3] *= 0.001
        mask = (np.asanyarray(image.dataobj) > 0).astype(np.uint8)
        derivatives[name] = surface_mask_consistency(surface, mask, affine, limit=limit)
        derivatives[name]["sha256"] = sha256(path)
        add(
            name,
            "heuristically_assessed",
            "INDETERMINATE",
            (
                "Same-pipeline foreground derivative consistency, not "
                "independent reference segmentation"
            ),
            {
                "path": str(path),
                "sha256": sha256(path),
                "threshold": ">0 supplied derivative; no new segmentation",
            },
        )
    for name in [
        "independent_tissue_reference",
        "MRI_anatomical_plausibility",
        "independent_registration_truth",
    ]:
        add(
            name,
            "not_assessed",
            "INDETERMINATE",
            "No independent validated tissue/landmark evidence available",
            {"participant": assets.subject},
        )
    add(
        "segmentation_source",
        "heuristically_assessed",
        "INDETERMINATE",
        "Supplied FreeSurfer aseg label inventory, not independently validated tissue truth",
        {"path": str(assets.subject_dir / "mri/aseg.mgz")},
    )
    aseg = assets.subject_dir / "mri/aseg.mgz"
    label_inventory = None
    if aseg.exists():
        image = nib.load(aseg)
        labels, counts = np.unique(np.asanyarray(image.dataobj), return_counts=True)
        label_inventory = {
            "sha256": sha256(aseg),
            "labels": labels.astype(int).tolist(),
            "counts": counts.tolist(),
        }
    gaps = [
        distance_to_surface(inner.vertices, outer).tolist()
        for inner, outer in zip(model.surfaces.meshes[:-1], model.surfaces.meshes[1:], strict=True)
    ]
    return {
        "status": evidence_state(records),
        "records": [r.to_dict() for r in records],
        "derivative_checks": derivatives,
        "aseg_inventory": label_inventory,
        "inner_vertex_to_outer_triangle_separations_m": gaps,
        "clinical_certification": False,
        "anatomical_certification": False,
        "SPM_foreground_status": "M7 rejection preserved; unrelated SPM mask is not a conductor",
        "future_backend_contract": (
            "subject/frame/unit/provenance, ordered tissue labels, "
            "external validation and mask uncertainty required"
        ),
    }
