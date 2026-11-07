"""Validated conductor geometry, exact bounded scalp distances and optional generation."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import mne
import numpy as np
from scipy.spatial import cKDTree

from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import _point_triangle, nested_boundaries
from soma.imaging.surfaces import Mesh


class Readiness(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


def tri_state(conditions: dict[str, bool | None]) -> str:
    return (
        Readiness.FAIL
        if any(v is False for v in conditions.values())
        else Readiness.INDETERMINATE
        if any(v is None for v in conditions.values())
        else Readiness.PASS
    )


@dataclass(frozen=True)
class ConductorSurfaces:
    subject: str
    meshes: tuple[Mesh, Mesh, Mesh]
    native: Any
    provenance: dict[str, Any]

    @classmethod
    def from_mne(
        cls, subject: str, surfaces: Any, provenance: dict[str, Any]
    ) -> "ConductorSurfaces":
        by_id = {int(s["id"]): s for s in surfaces}
        if set(by_id) != {1, 3, 4}:
            raise ValueError("EEG requires exactly inner skull/outer skull/scalp IDs 1/3/4")
        if not subject or not provenance:
            raise ValueError("Surface subject and generation provenance required")
        ordered = [by_id[k] for k in (1, 3, 4)]
        if any(int(s["coord_frame"]) != 5 for s in ordered):
            raise ValueError("Conductor surfaces require MRI coordinates in metres")
        meshes = tuple(
            Mesh(
                Points(s["rr"], Frame.MRI),
                s["tris"],
                {"subject": subject, "boundary_id": int(s["id"]), **provenance},
            )
            for s in ordered
        )
        return cls(subject, meshes, ordered, provenance)  # type: ignore[arg-type]

    def readiness(
        self,
        *,
        sensor_compatible: bool | None,
        minimum_separation_m: float = 0.0001,
        minimum_quality: float = 0.01,
        anatomical_evidence: bool | None = None,
    ) -> dict[str, Any]:
        nesting = nested_boundaries(list(self.meshes), minimum_separation_m=minimum_separation_m)
        quality = nesting["quality"]
        topology = all(
            q["boundary_edges"]
            == q["nonmanifold_edges"]
            == q["nonmanifold_vertices"]
            == q["degenerate_triangles"]
            == q["duplicate_faces"]
            == q["inconsistent_oriented_edges"]
            == 0
            and q["connected_components"] == 1
            for q in quality
        )
        checks = {
            "topology": bool(topology),
            "geometry": bool(nesting["geometric_candidate"]),
            "anatomical_evidence": anatomical_evidence,
            "coordinate_consistency": all(m.vertices.frame == Frame.MRI for m in self.meshes),
            "sensor_compatibility": sensor_compatible,
            "numerical_mesh_quality": all(
                q["triangle_quality_min"] >= minimum_quality for q in quality
            ),
        }
        computational = {k: v for k, v in checks.items() if k != "anatomical_evidence"}
        return {
            "status": tri_state(checks),
            "checks": {
                k: {"status": tri_state({k: v}), "supported": v is not None}
                for k, v in checks.items()
            },
            "computational_readiness": tri_state(computational),
            "subject": self.subject,
            "boundaries": ["inner_skull", "outer_skull", "outer_scalp"],
            "quality": quality,
            "nesting": {k: v for k, v in nesting.items() if k != "quality"},
            "minimum_separation_m": minimum_separation_m,
            "intersection_tolerance_m": 1e-8,
            "minimum_triangle_quality": minimum_quality,
            "anatomical_certification": False,
            "clinical_certification": False,
            "unsupported_required_checks": [k for k, v in checks.items() if v is None],
            "surface_provenance": self.provenance,
        }


def distance_to_surface(points: Points, mesh: Mesh) -> np.ndarray[Any, Any]:
    if points.frame != mesh.vertices.frame:
        raise ValueError("Distance query mixes coordinate frames")
    triangles = mesh.vertices.xyz[mesh.faces]
    centers = triangles.mean(axis=1)
    radii = np.linalg.norm(triangles - centers[:, None], axis=2).max(axis=1)
    tree = cKDTree(centers)
    upper = cKDTree(mesh.vertices.xyz).query(points.xyz)[0]
    output = []
    for point, bound in zip(points.xyz, upper, strict=True):
        candidates = tree.query_ball_point(point, float(bound + radii.max() + 1e-12))
        distances = _point_triangle(
            np.repeat(point[None], len(candidates), axis=0), triangles[candidates]
        )
        output.append(float(distances.min()))
    return np.asarray(output)


def generate_watershed(
    subject: str, subjects_dir: Path, *, output_exists_policy: str = "refuse"
) -> dict[str, Any]:
    import shutil

    if output_exists_policy != "refuse":
        raise ValueError("Watershed overwrite is not supported by this adapter")
    if not shutil.which("mri_watershed"):
        raise RuntimeError(
            "Optional watershed requires installed/configured FreeSurfer; no "
            "generated boundaries substituted"
        )
    mne.bem.make_watershed_bem(
        subject, subjects_dir=subjects_dir, overwrite=False, show=False, verbose=False
    )
    return {
        "subject": subject,
        "method": "MNE watershed",
        "overwrite": False,
        "source": "participant T1 MRI",
        "anatomical_truth_claim": False,
    }
