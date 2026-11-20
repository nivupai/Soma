"""Cortical white/pial midsurface source space with explicit exclusions and evidence.

Sources are vertices of the per-hemisphere midsurface (vertexwise mean of white and
pial surfaces sharing one FreeSurfer topology), chosen by a count-matched ico/oct
subdivision on the subject sphere. Each source carries an outward area-weighted
normal and the barycentric area of the full-resolution vertices nearest to it on the
sphere. Nothing is silently dropped: every excluded vertex or candidate source is
counted under a named reason. This complements, and never replaces, the volumetric
``SourceDomain``; area weights (m^2) and voxel volumes (m^3) are different measures.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import ConvexHull, cKDTree

from soma.anatomy.surfaces import distance_to_surface
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains, mesh_quality
from soma.imaging.surfaces import Mesh
from soma.source.priors import vertex_areas

Array = NDArray[np.float64]
IntArray = NDArray[np.int64]

SCHEMA = "soma.cortical-source-space/1"
FRAME = "MRI_surface_RAS_m"
HEMISPHERES = ("lh", "rh")
DEFAULT_EXCLUDED_LABELS = ("unknown", "corpuscallosum")
UNLABELLED = "unlabelled (aparc -1; FreeSurfer medial wall)"
COVERAGE_DEFINITIONS = {
    "area_fraction_of_midsurface": (
        "sum of retained source patch areas / total midsurface area of both hemispheres "
        "(barycentric vertex areas; medial wall and every excluded patch count against it)"
    ),
    "area_fraction_of_eligible_cortex": (
        "sum of retained source patch areas / midsurface area after label exclusions "
        "(fraction lost only to containment/orientation exclusions)"
    ),
    "full_resolution_vertices_represented_fraction": (
        "full-resolution vertices whose patch is assigned to a retained source / all "
        "full-resolution vertices"
    ),
    "vertex_fraction_retained": (
        "retained sources / full-resolution vertices (decimation ratio, not coverage)"
    ),
}


def parse_spacing(spacing: str) -> tuple[str, int, int]:
    """Return (base, grade, vertex count) count-matched to MNE ``ico``/``oct`` spacing."""
    match = re.fullmatch(r"(ico|oct)([1-7])", spacing)
    if match is None:
        raise ValueError("Spacing must be ico1..ico7 or oct1..oct7")
    base, grade = match.group(1), int(match.group(2))
    count = 10 * 4**grade + 2 if base == "ico" else 4 * 4 ** (grade - 1) + 2
    return base, grade, count


def subdivided_sphere(spacing: str) -> Array:
    """Unit-sphere vertices of a midpoint-subdivided icosahedron or octahedron."""
    base, grade, count = parse_spacing(spacing)
    if base == "ico":
        phi = (1 + 5**0.5) / 2
        seed = []
        for a in (-1.0, 1.0):
            for b in (-phi, phi):
                seed += [[0.0, a, b], [a, b, 0.0], [b, 0.0, a]]
        v = np.asarray(seed, float)
        steps = grade
    else:
        v = np.vstack([np.eye(3), -np.eye(3)])
        steps = grade - 1
    v /= np.linalg.norm(v, axis=1)[:, None]
    f = np.asarray(ConvexHull(v).simplices, dtype=np.int64)
    for _ in range(steps):
        edges = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        unique, inverse = np.unique(edges, axis=0, return_inverse=True)
        mid = v[unique].mean(axis=1)
        mid /= np.linalg.norm(mid, axis=1)[:, None]
        m = inverse.reshape(3, -1) + len(v)
        a, b, c = f.T
        ab, bc, ca = m
        f = np.vstack([np.c_[a, ab, ca], np.c_[ab, b, bc], np.c_[ca, bc, c], np.c_[ab, bc, ca]])
        v = np.vstack([v, mid])
    if len(v) != count:
        raise AssertionError("Subdivision count mismatch")
    return np.asarray(v, float)


def vertex_normals(vertices_m: Array, faces: IntArray) -> Array:
    """Unit area-weighted vertex normals following face winding (outward for FreeSurfer)."""
    tri = vertices_m[faces]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n = np.zeros_like(vertices_m)
    for i in range(3):
        np.add.at(n, faces[:, i], face)
    length = np.linalg.norm(n, axis=1)
    if np.any(length <= 0):
        raise ValueError("Vertex without positive incident area has no normal")
    return np.asarray(n / length[:, None], float)


def signed_volume_m3(vertices_m: Array, faces: IntArray) -> float:
    t = vertices_m[faces]
    return float(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6)


@dataclass(frozen=True)
class HemisphereSurfaces:
    """One hemisphere's white/pial/sphere surfaces with shared topology and labels."""

    hemisphere: str
    white_m: Array
    pial_m: Array
    sphere: Array
    faces: IntArray
    labels: IntArray
    label_names: tuple[str, ...]
    provenance: dict[str, Any] = field(default_factory=dict)
    frame: str = FRAME

    def __post_init__(self) -> None:
        w, p, s = (np.asarray(x, float) for x in (self.white_m, self.pial_m, self.sphere))
        f, lab = np.asarray(self.faces), np.asarray(self.labels)
        n = len(w)
        if (
            self.hemisphere not in HEMISPHERES
            or self.frame != FRAME
            or w.ndim != 2
            or w.shape[1] != 3
            or n < 4
            or p.shape != w.shape
            or s.shape != w.shape
            or not all(np.isfinite(x).all() for x in (w, p, s))
            or f.ndim != 2
            or f.shape[1] != 3
            or f.dtype.kind not in "iu"
            or not len(f)
            or np.min(f) < 0
            or np.max(f) >= n
            or lab.shape != (n,)
            or lab.dtype.kind not in "iu"
            or np.min(lab) < -1
            or np.max(lab) >= len(self.label_names)
        ):
            raise ValueError("Matched white/pial/sphere topology, labels and surface-RAS required")
        if max(np.max(np.abs(w)), np.max(np.abs(p))) > 0.2:
            raise ValueError("Cortical surfaces must be in metres")
        r = np.linalg.norm(s, axis=1)
        if np.any(r <= 0):
            raise ValueError("Sphere vertices must be nonzero")
        values = {
            "white_m": w,
            "pial_m": p,
            "sphere": s / r[:, None],
            "faces": f.astype(np.int64),
            "labels": lab.astype(np.int64),
        }
        for name, value in values.items():
            value = value.copy()
            value.flags.writeable = False
            object.__setattr__(self, name, value)

    @classmethod
    def from_freesurfer(
        cls, subject_dir: Path, hemisphere: str, *, annotation: str = "aparc"
    ) -> "HemisphereSurfaces":
        from nibabel.freesurfer.io import read_annot, read_geometry

        def geometry(name: str) -> tuple[Array, IntArray]:
            v, f = read_geometry(str(subject_dir / "surf" / f"{hemisphere}.{name}"))
            return np.asarray(v, float), np.asarray(f, np.int64)

        white, faces = geometry("white")
        pial, pial_faces = geometry("pial")
        sphere, sphere_faces = geometry("sphere")
        if not (np.array_equal(faces, pial_faces) and np.array_equal(faces, sphere_faces)):
            raise ValueError("White, pial and sphere surfaces must share topology")
        path = subject_dir / "label" / f"{hemisphere}.{annotation}.annot"
        labels, _, names = read_annot(str(path))
        return cls(
            hemisphere,
            white * 0.001,
            pial * 0.001,
            sphere,
            np.asarray(faces, np.int64),
            np.asarray(labels, np.int64),
            tuple(n.decode() if isinstance(n, bytes) else str(n) for n in names),
            {"surfaces": ["white", "pial", "sphere"], "annotation": annotation, "units": "mm"},
        )

    @property
    def midsurface_m(self) -> Array:
        return np.asarray((self.white_m + self.pial_m) / 2, float)

    def region_counts(self, vertices: IntArray) -> dict[str, int]:
        """Annotation region name counts for the given vertices (unlabelled named)."""
        values, counts = np.unique(self.labels[vertices], return_counts=True)
        return {
            UNLABELLED if v < 0 else self.label_names[int(v)]: int(c)
            for v, c in zip(values, counts, strict=True)
        }

    def label_masks(
        self, excluded_labels: tuple[str, ...], exclude_unlabelled: bool
    ) -> dict[str, NDArray[np.bool_]]:
        """Full-resolution exclusion masks by name, including zero-count names."""
        masks: dict[str, NDArray[np.bool_]] = {}
        for name in excluded_labels:
            index = [i for i, n in enumerate(self.label_names) if n == name]
            masks[name] = np.isin(self.labels, index)
        if exclude_unlabelled:
            masks[UNLABELLED] = self.labels == -1
        return masks


@dataclass(frozen=True)
class CorticalSourceSpace:
    """Retained cortical sources; ``report`` is the public aggregate evidence."""

    hemispheres: tuple[str, ...]
    vertices: tuple[IntArray, ...]
    positions_m: Array
    normals: Array
    areas_m2: Array
    spacing: str
    report: dict[str, Any]
    frame: str = FRAME

    def __post_init__(self) -> None:
        p, n, a = (np.asarray(x, float) for x in (self.positions_m, self.normals, self.areas_m2))
        count = sum(len(v) for v in self.vertices)
        if (
            self.frame != FRAME
            or len(self.hemispheres) != len(self.vertices)
            or not count
            or p.shape != (count, 3)
            or n.shape != (count, 3)
            or a.shape != (count,)
            or not all(np.isfinite(x).all() for x in (p, n, a))
            or np.any(a <= 0)
            or not np.allclose(np.linalg.norm(n, axis=1), 1, rtol=0, atol=1e-9)
            or len(np.unique(p, axis=0)) != count
        ):
            raise ValueError("Finite unique sources, unit normals and positive areas required")
        for name, value in {"positions_m": p, "normals": n, "areas_m2": a}.items():
            value = value.copy()
            value.flags.writeable = False
            object.__setattr__(self, name, value)
        frozen = []
        for v in self.vertices:
            v = np.asarray(v, np.int64).copy()
            v.flags.writeable = False
            frozen.append(v)
        object.__setattr__(self, "vertices", tuple(frozen))

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{h}:{int(i)}" for h, v in zip(self.hemispheres, self.vertices, strict=True) for i in v
        )

    @property
    def total_area_m2(self) -> float:
        return float(self.areas_m2.sum())

    @property
    def identity(self) -> str:
        # MRI-derived fingerprint: private provenance only, never public exports.
        digest = hashlib.sha256(self.frame.encode() + self.spacing.encode())
        for h, v in zip(self.hemispheres, self.vertices, strict=True):
            digest.update(h.encode() + v.astype("<i8").tobytes())
        for x in (self.positions_m, self.normals, self.areas_m2):
            digest.update(x.astype("<f8").tobytes())
        return digest.hexdigest()


def _inner_skull_gate(inner_skull: Mesh) -> dict[str, Any]:
    if inner_skull.vertices.frame != Frame.MRI or np.max(np.abs(inner_skull.vertices.xyz)) > 0.2:
        raise ValueError("Inner skull must be an MRI-frame surface in metres")
    q = mesh_quality(inner_skull)
    if not q["geometrically_valid_under_checks"] or not q["outward_global_winding"]:
        raise ValueError("Inner skull must be closed, manifold and outward wound")
    return {
        "vertex_count": int(q["vertex_count"]),
        "face_count": int(q["face_count"]),
        "outward_global_winding": True,
        "geometrically_valid_under_checks": True,
    }


def build_cortical_source_space(
    hemispheres: list[HemisphereSurfaces],
    inner_skull: Mesh,
    *,
    spacing: str = "oct6",
    excluded_labels: tuple[str, ...] = DEFAULT_EXCLUDED_LABELS,
    exclude_unlabelled: bool = True,
    minimum_margin_m: float = 0.0,
    minimum_thickness_m: float = 1e-5,
) -> CorticalSourceSpace:
    """Decimate, orient, weight and gate cortical sources; record every exclusion.

    Exclusion order per candidate source: anatomical label (by name), undefined
    white->pial direction (thickness below ``minimum_thickness_m``), normal opposing
    white->pial, outside the inner skull, inner-skull margin below ``minimum_margin_m``.
    Patch areas of excluded candidates are not redistributed to retained sources.
    """
    _, _, count = parse_spacing(spacing)
    names = [h.hemisphere for h in hemispheres]
    if not hemispheres or len(set(names)) != len(names):
        raise ValueError("Unique hemispheres required")
    if not np.isfinite(minimum_margin_m) or minimum_margin_m < 0 or minimum_thickness_m <= 0:
        raise ValueError("Nonnegative finite margin and positive thickness threshold required")
    skull = _inner_skull_gate(inner_skull)
    ico = subdivided_sphere(spacing)
    reasons = (
        "orientation_undefined_zero_thickness",
        "normal_opposes_white_to_pial",
        "outside_inner_skull",
        "inner_skull_margin_below_minimum",
    )
    kept_vertices: list[IntArray] = []
    positions, normals, areas = [], [], []
    exclusions: list[dict[str, Any]] = []
    hemi_reports: dict[str, Any] = {}
    totals = {"area": 0.0, "eligible_area": 0.0, "vertices": 0, "represented": 0}
    margins: list[Array] = []
    kept_margins: list[Array] = []
    cosines: list[Array] = []
    candidates_total = 0
    for h in hemispheres:
        mid = h.midsurface_m
        area = np.asarray(vertex_areas(mid, h.faces), float)
        volume = signed_volume_m3(mid, h.faces)
        if volume <= 0:
            raise ValueError("Midsurface winding is not outward; normals would be inverted")
        normal = vertex_normals(mid, h.faces)
        masks = h.label_masks(excluded_labels, exclude_unlabelled)
        excluded = np.zeros(len(mid), bool)
        for m in masks.values():
            excluded |= m
        candidates = np.unique(cKDTree(h.sphere).query(ico)[1]).astype(np.int64)
        candidates_total += len(candidates)
        for name, m in masks.items():
            exclusions.append(
                {
                    "hemisphere": h.hemisphere,
                    "reason": "anatomical_label",
                    "label": name,
                    "full_resolution_vertices": int(m.sum()),
                    "area_mm2": float(area[m].sum() * 1e6),
                    "candidate_sources": int(m[candidates].sum()),
                    "candidate_regions": {name: int(m[candidates].sum())},
                }
            )
        eligible = candidates[~excluded[candidates]]
        if not len(eligible):
            raise ValueError("No eligible cortical candidates after label exclusions")
        # Sphere-nearest patch of every eligible full-resolution vertex.
        owner = np.full(len(mid), -1, np.int64)
        members = np.flatnonzero(~excluded)
        owner[members] = cKDTree(h.sphere[eligible]).query(h.sphere[members])[1]
        patch = np.bincount(owner[members], weights=area[members], minlength=len(eligible))
        patch_vertices = np.bincount(owner[members], minlength=len(eligible))
        direction = h.pial_m[eligible] - h.white_m[eligible]
        thickness = np.linalg.norm(direction, axis=1)
        cos = np.full(len(eligible), np.nan)
        defined = thickness >= minimum_thickness_m
        cos[defined] = np.einsum(
            "ij,ij->i", normal[eligible][defined], direction[defined] / thickness[defined, None]
        )
        p = mid[eligible]
        inside = np.asarray(contains(inner_skull, p), bool)
        margin = distance_to_surface(Points(p, Frame.MRI), inner_skull)
        margin = np.where(inside, margin, -margin)
        status = np.zeros(len(eligible), np.int64)  # 0 kept, 1+ index of first failed reason
        for code, failed in enumerate(
            [
                ~defined,
                defined & ~(np.nan_to_num(cos, nan=1.0) > 0),
                ~inside,
                inside & (margin < minimum_margin_m),
            ],
            start=1,
        ):
            status[(status == 0) & failed] = code
        for code, reason in enumerate(reasons, start=1):
            bad = status == code
            exclusions.append(
                {
                    "hemisphere": h.hemisphere,
                    "reason": reason,
                    "label": None,
                    "full_resolution_vertices": int(patch_vertices[bad].sum()),
                    "area_mm2": float(patch[bad].sum() * 1e6),
                    "candidate_sources": int(bad.sum()),
                    "candidate_regions": h.region_counts(eligible[bad]),
                }
            )
        keep = status == 0
        if not keep.any():
            raise ValueError("No cortical source passed orientation and containment gates")
        kept_vertices.append(eligible[keep])
        positions.append(p[keep])
        normals.append(normal[eligible][keep])
        areas.append(patch[keep])
        margins.append(margin)
        kept_margins.append(margin[keep])
        cosines.append(cos[defined])
        totals["area"] += float(area.sum())
        totals["eligible_area"] += float(area[~excluded].sum())
        totals["vertices"] += len(mid)
        totals["represented"] += int(patch_vertices[keep].sum())
        hemi_reports[h.hemisphere] = {
            "full_resolution_vertices": len(mid),
            "midsurface_area_mm2": float(area.sum() * 1e6),
            "label_excluded_vertices": int(excluded.sum()),
            "candidate_sources": len(candidates),
            "eligible_candidates": len(eligible),
            "sources": int(keep.sum()),
            "retained_area_mm2": float(patch[keep].sum() * 1e6),
            "midsurface_signed_volume_mm3": volume * 1e9,
        }
    position = np.vstack(positions)
    normal_all = np.vstack(normals)
    area_all = np.concatenate(areas)
    margin_all = np.concatenate(margins)
    margin_kept = np.concatenate(kept_margins)
    cos_all = np.concatenate(cosines)
    kept = len(position)
    retained = float(area_all.sum())
    kept_cos = np.concatenate(
        [
            np.einsum(
                "ij,ij->i",
                n,
                (h.pial_m[v] - h.white_m[v])
                / np.linalg.norm(h.pial_m[v] - h.white_m[v], axis=1)[:, None],
            )
            for h, v, n in zip(hemispheres, kept_vertices, normals, strict=True)
        ]
    )
    final_inside = np.asarray(contains(inner_skull, position), bool)
    if not final_inside.all() or np.any(kept_cos <= 0):
        raise AssertionError("Retained sources must satisfy containment and orientation gates")
    by_reason = {
        r: int(sum(e["candidate_sources"] for e in exclusions if e["reason"] == r))
        for r in ("anatomical_label", *reasons)
    }
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "frame": FRAME,
        "units": {"positions": "m", "areas": "m2 (reported as mm2)", "normals": "unit"},
        "surface": "white/pial midsurface: vertexwise mean of white and pial, shared topology",
        "spacing": spacing,
        "spacing_definition": (
            f"{spacing}: {count} unit-sphere vertices per hemisphere (count-matched to MNE; "
            "not vertex-identical), each mapped to its nearest subject-sphere vertex; "
            "duplicates merged"
        ),
        "weights": (
            "barycentric midsurface vertex area of every eligible full-resolution vertex, "
            "assigned to its sphere-nearest eligible candidate; excluded patches are not "
            "redistributed"
        ),
        "normals": "area-weighted midsurface vertex normals from outward FreeSurfer winding",
        "hemispheres": hemi_reports,
        "counts": {
            "full_resolution_vertices": totals["vertices"],
            "candidate_sources": candidates_total,
            "sources": kept,
            "excluded_candidates_by_reason": by_reason,
        },
        "coverage": {
            "area_fraction_of_midsurface": retained / totals["area"],
            "area_fraction_of_eligible_cortex": retained / totals["eligible_area"],
            "full_resolution_vertices_represented_fraction": totals["represented"]
            / totals["vertices"],
            "vertex_fraction_retained": kept / totals["vertices"],
            "midsurface_area_mm2": totals["area"] * 1e6,
            "retained_area_mm2": retained * 1e6,
            "definitions": COVERAGE_DEFINITIONS,
        },
        "containment": {
            "surface": "inner skull",
            "inner_skull": skull,
            "test": "generalized winding number (soma.imaging.mesh_quality.contains)",
            "minimum_margin_m": minimum_margin_m,
            "tested_candidates": len(margin_all),
            "inside_candidates": int((margin_all > 0).sum()),
            "outside_candidates": int((margin_all <= 0).sum()),
            "candidate_signed_margin_min_mm": float(np.min(margin_all) * 1e3),
            "retained_sources_inside": int(final_inside.sum()),
            "retained_margin_min_mm": float(np.min(margin_kept) * 1e3),
            "retained_margin_median_mm": float(np.median(margin_kept) * 1e3),
            "retained_below_mm": {str(t): int((margin_kept < t * 1e-3).sum()) for t in (1, 2, 5)},
            "all_retained_inside": True,
        },
        "orientation": {
            "check": "cosine between source normal and unit white->pial vector",
            "minimum_thickness_m": minimum_thickness_m,
            "defined_candidates": len(cos_all),
            "outward_candidates": int((cos_all > 0).sum()),
            "outward_fraction_of_defined": float((cos_all > 0).mean()) if len(cos_all) else None,
            "cosine_median": float(np.median(cos_all)) if len(cos_all) else None,
            "cosine_min": float(np.min(cos_all)) if len(cos_all) else None,
            "retained_cosine_min": float(np.min(kept_cos)),
            "retained_cosine_median": float(np.median(kept_cos)),
            "global_midsurface_winding_outward": True,
        },
        "exclusions": exclusions,
        "volumetric_option": "soma.source.domains.SourceDomain unchanged",
        "anatomical_accuracy_established": False,
    }
    return CorticalSourceSpace(
        tuple(names),
        tuple(kept_vertices),
        position,
        normal_all,
        area_all,
        spacing,
        report,
    )
