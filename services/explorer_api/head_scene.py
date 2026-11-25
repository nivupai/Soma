"""Public 3D head scene and per-source uncertainty overlay contracts (M35).

The only head served here is generated in code: four nested, star-shaped shells
(scalp, outer skull, inner skull, folded cortex) on a shared icosphere, synthetic
10-20 sensor positions and a synthetic cortical-surface source space. No MRI,
participant or private asset is read. Private anatomy stays on the opt-in,
loopback-only M32 routes in ``anatomical_models``; nothing here relaxes them.

Readiness is derived with Soma's own ``classify_anatomy``: a synthetic head is
not MRI-derived, so it is ``NOT_READY`` even though its geometry passes the
checks performed here. "Geometrically valid" and "anatomically validated" are
separate fields and never inferred from each other.

The uncertainty overlay is a deterministic MOCK fixture standing in for the M34
localisation-error results, which do not exist yet. Its values carry no
scientific meaning; the contract shape is what the endpoint fixes.
"""

from functools import lru_cache
from typing import Final, Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator

from soma.anatomy.head_models import classify_anatomy

from .models import Strict

DEMO_HEAD_ID = "demo-synthetic-head"
HEAD_SCENE_CONTRACT: Final = "soma.explorer.head-scene/1"
OVERLAY_CONTRACT: Final = "soma.explorer.source-uncertainty-overlay/1"

Readiness = Literal["VALIDATED", "QC_ONLY", "NOT_READY"]
LayerName = Literal["scalp", "outer_skull", "inner_skull", "cortex"]

READINESS_LABELS: dict[str, Readiness] = {
    "VALIDATED_ANATOMY": "VALIDATED",
    "QC_ONLY_ANATOMY": "QC_ONLY",
    "NOT_READY_FOR_FORWARD_MODEL": "NOT_READY",
}

# Semi-axis ratios (x right, y anterior, z superior) shared by all shells, so the
# layers stay concentric along every ray. Radii in mm along +y.
_AXES = np.array([0.79, 1.0, 0.89])
_LAYER_RADII_MM: list[tuple[LayerName, str, float]] = [
    ("scalp", "Scalp", 95.0),
    ("outer_skull", "Outer skull", 89.0),
    ("inner_skull", "Inner skull", 83.0),
    ("cortex", "Brain / cortex", 77.0),
]
_FOLD_AMPLITUDE = 0.025
_SOURCE_DEPTH_MM = 3.0
_SENSOR_ANGLES_DEG: list[tuple[str, float, float]] = [
    # (label, polar angle from vertex, azimuth from anterior; + is right)
    ("Fp1", 90, -18),
    ("Fp2", 90, 18),
    ("F7", 90, -54),
    ("F3", 60, -40),
    ("Fz", 45, 0),
    ("F4", 60, 40),
    ("F8", 90, 54),
    ("T7", 90, -90),
    ("C3", 45, -90),
    ("Cz", 0, 0),
    ("C4", 45, 90),
    ("T8", 90, 90),
    ("P7", 90, -126),
    ("P3", 60, -140),
    ("Pz", 45, 180),
    ("P4", 60, 140),
    ("P8", 90, 126),
    ("O1", 90, -162),
    ("Oz", 90, 180),
    ("O2", 90, 162),
]


class GeometryChecks(Strict):
    closed_manifold: bool
    finite_coordinates: bool
    nested_layers: bool
    sensors_on_scalp: bool
    sources_inside_cortex: bool
    minimum_layer_gap_mm: float
    method: str


class HeadLayer(Strict):
    name: LayerName
    label: str
    vertices_mm: list[list[float]]
    faces: list[list[int]]


class Sensor(Strict):
    label: str
    position_mm: list[float] = Field(min_length=3, max_length=3)


class SourceSpace(Strict):
    kind: Literal["cortical_surface"]
    positions_mm: list[list[float]]
    normals: list[list[float]]
    scalar_name: str
    scalar_units: str
    scalar: list[float]

    @model_validator(mode="after")
    def _aligned(self) -> "SourceSpace":
        n = len(self.positions_mm)
        if len(self.normals) != n or len(self.scalar) != n:
            raise ValueError("Source positions, normals and scalar must align")
        return self


class HeadScene(Strict):
    contract: Literal["soma.explorer.head-scene/1"]
    head_id: str
    label: str
    synthetic: bool
    redistributable: bool
    private_mri_used: Literal[False]
    generator: str
    frame: str
    units: Literal["mm"]
    readiness: Readiness
    readiness_status: str
    readiness_reasons: list[str]
    geometrically_valid: bool
    anatomically_validated: bool
    geometry_checks: GeometryChecks
    layers: list[HeadLayer]
    sensors: list[Sensor]
    sources: SourceSpace
    warnings: list[str]

    @model_validator(mode="after")
    def _honest(self) -> "HeadScene":
        if self.anatomically_validated and self.readiness != "VALIDATED":
            raise ValueError("Anatomical validation requires VALIDATED readiness")
        if self.synthetic and self.anatomically_validated:
            raise ValueError("Synthetic geometry cannot be anatomically validated")
        return self


class SourceUncertaintyOverlay(Strict):
    contract: Literal["soma.explorer.source-uncertainty-overlay/1"]
    head_id: str
    quantity: Literal["localisation_error"]
    units: Literal["mm"]
    statistic: Literal["mean"]
    interval: Literal["confidence_interval"]
    confidence_level: float = Field(gt=0, lt=1)
    n_sources: int = Field(ge=0)
    mean: list[float]
    lower: list[float]
    upper: list[float]
    origin: Literal["MOCK_FIXTURE", "M34_RESULT"]
    fixture: bool
    warnings: list[str]

    @model_validator(mode="after")
    def _intervals(self) -> "SourceUncertaintyOverlay":
        if not (len(self.mean) == len(self.lower) == len(self.upper) == self.n_sources):
            raise ValueError("Uncertainty arrays must have one value per source")
        if any(
            not (0 <= lo <= m <= hi)
            for lo, m, hi in zip(self.lower, self.mean, self.upper, strict=True)
        ):
            raise ValueError("Each source requires 0 <= lower <= mean <= upper")
        if self.fixture != (self.origin == "MOCK_FIXTURE"):
            raise ValueError("Fixture flag must match the declared origin")
        return self


class HeadSceneSummary(Strict):
    head_id: str
    label: str
    synthetic: bool
    readiness: Readiness


def icosphere(level: int) -> tuple[np.ndarray, np.ndarray]:
    """Unit icosphere with outward-wound triangles."""
    t = (1 + 5**0.5) / 2
    v = [
        [-1, t, 0],
        [1, t, 0],
        [-1, -t, 0],
        [1, -t, 0],
        [0, -1, t],
        [0, 1, t],
        [0, -1, -t],
        [0, 1, -t],
        [t, 0, -1],
        [t, 0, 1],
        [-t, 0, -1],
        [-t, 0, 1],
    ]
    faces = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]
    vertices = [np.asarray(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(level):
        cache: dict[tuple[int, int], int] = {}
        refined = []
        for a, b, c in faces:
            ab, bc, ca = (_midpoint(vertices, cache, x, y) for x, y in [(a, b), (b, c), (c, a)])
            refined += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        faces = refined
    return np.asarray(vertices), np.asarray(faces, dtype=np.int64)


def _midpoint(vertices: list[np.ndarray], cache: dict[tuple[int, int], int], a: int, b: int) -> int:
    key = (min(a, b), max(a, b))
    if key not in cache:
        m = vertices[a] + vertices[b]
        vertices.append(m / np.linalg.norm(m))
        cache[key] = len(vertices) - 1
    return cache[key]


def _fold(directions: np.ndarray) -> np.ndarray:
    """Smooth gyral-like radial modulation, 1 +/- _FOLD_AMPLITUDE."""
    azimuth = np.arctan2(directions[:, 0], directions[:, 1])
    polar = np.arccos(np.clip(directions[:, 2], -1, 1))
    return np.asarray(1 + _FOLD_AMPLITUDE * np.sin(7 * azimuth) * np.sin(5 * polar), float)


def _shell(directions: np.ndarray, radius_mm: np.ndarray | float) -> np.ndarray:
    return np.asarray(directions * _AXES * np.reshape(radius_mm, (-1, 1)), float)


def _closed_manifold(faces: np.ndarray) -> bool:
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(counts == 2))


def _ellipsoid_radius(points: np.ndarray, radius_mm: float) -> np.ndarray:
    """Points' normalized ellipsoidal radius relative to a shell of radius_mm."""
    return np.asarray(np.linalg.norm(points / _AXES, axis=1) / radius_mm, float)


@lru_cache(maxsize=1)
def demo_head_scene() -> HeadScene:
    directions, faces = icosphere(3)
    radii = {name: r for name, _, r in _LAYER_RADII_MM}
    layer_points: dict[str, np.ndarray] = {}
    for name, _, r in _LAYER_RADII_MM:
        scale = r * _fold(directions) if name == "cortex" else r
        layer_points[name] = _shell(directions, scale)
    order = [name for name, _, _ in _LAYER_RADII_MM]
    gaps = [
        np.linalg.norm(layer_points[a], axis=1) - np.linalg.norm(layer_points[b], axis=1)
        for a, b in zip(order, order[1:], strict=False)
    ]
    min_gap = float(min(np.min(g) for g in gaps))

    sensor_points = []
    for _, polar_deg, azimuth_deg in _SENSOR_ANGLES_DEG:
        p, a = np.radians(polar_deg), np.radians(azimuth_deg)
        d = np.array([np.sin(p) * np.sin(a), np.sin(p) * np.cos(a), np.cos(p)])
        # Ray/ellipsoid intersection for the scalp shell.
        sensor_points.append(d * radii["scalp"] / np.linalg.norm(d / _AXES))
    sensors = np.asarray(sensor_points)

    source_dirs, _ = icosphere(2)
    cortex_r = radii["cortex"] * _fold(source_dirs)
    source_points = _shell(source_dirs, cortex_r - _SOURCE_DEPTH_MM)
    normals = source_points / np.linalg.norm(source_points, axis=1, keepdims=True)
    centre = np.array([-np.sin(np.pi / 4), 0.0, np.cos(np.pi / 4)])  # near C3
    angle = np.arccos(np.clip(source_dirs @ centre, -1, 1))
    activation = np.exp(-(angle**2) / (2 * 0.35**2))

    finite = all(bool(np.isfinite(p).all()) for p in layer_points.values()) and bool(
        np.isfinite(sensors).all() and np.isfinite(source_points).all()
    )
    on_scalp = bool(np.all(np.abs(_ellipsoid_radius(sensors, radii["scalp"]) - 1) < 1e-6))
    inside = bool(
        np.all(np.linalg.norm(source_points / _AXES, axis=1) < cortex_r)
        and np.all(np.linalg.norm(source_points, axis=1) > 0)
    )
    checks = GeometryChecks(
        closed_manifold=_closed_manifold(faces),
        finite_coordinates=finite,
        nested_layers=min_gap > 0,
        sensors_on_scalp=on_scalp,
        sources_inside_cortex=inside,
        minimum_layer_gap_mm=round(min_gap, 3),
        method=(
            "Shared-direction star-shaped shells: nesting is the per-ray radial gap; "
            "edge-manifold count per shell; no self-intersection test beyond construction."
        ),
    )
    geometric = all(
        [
            checks.closed_manifold,
            checks.finite_coordinates,
            checks.nested_layers,
            checks.sensors_on_scalp,
            checks.sources_inside_cortex,
        ]
    )
    readiness = classify_anatomy(
        {
            "topology": checks.closed_manifold,
            "nesting": checks.nested_layers,
            "self_intersections": None,
            "coordinates": checks.finite_coordinates,
            "electrodes": checks.sensors_on_scalp,
            "sources": checks.sources_inside_cortex,
            "materials": None,
        },
        MRI_derived=False,
        local_permission=True,
    )

    def rows(a: np.ndarray, digits: int = 3) -> list[list[float]]:
        return [[round(float(x), digits) for x in row] for row in a]

    return HeadScene(
        contract=HEAD_SCENE_CONTRACT,
        head_id=DEMO_HEAD_ID,
        label="Synthetic concentric-shell head",
        synthetic=True,
        redistributable=True,
        private_mri_used=False,
        generator="services.explorer_api.head_scene.demo_head_scene (icosphere level 3)",
        frame="synthetic_head_RAS_mm",
        units="mm",
        readiness=READINESS_LABELS[readiness["status"]],
        readiness_status=readiness["status"],
        readiness_reasons=list(readiness["limitations"]),
        geometrically_valid=geometric,
        anatomically_validated=bool(readiness["anatomical_accuracy_established"]),
        geometry_checks=checks,
        layers=[
            HeadLayer(
                name=name, label=label, vertices_mm=rows(layer_points[name]), faces=faces.tolist()
            )
            for name, label, _ in _LAYER_RADII_MM
        ],
        sensors=[
            Sensor(label=label, position_mm=[round(float(x), 3) for x in p])
            for (label, _, _), p in zip(_SENSOR_ANGLES_DEG, sensors, strict=True)
        ],
        sources=SourceSpace(
            kind="cortical_surface",
            positions_mm=rows(source_points),
            normals=rows(normals, 5),
            scalar_name="synthetic_activation",
            scalar_units="a.u.",
            scalar=[round(float(x), 5) for x in activation],
        ),
        warnings=[
            "Synthetic geometry generated in code; it is not anatomy and is redistributable.",
            "Geometrically valid is not anatomically validated.",
            "Sensor positions are idealized 10-20 directions projected onto the synthetic scalp.",
        ],
    )


@lru_cache(maxsize=1)
def demo_uncertainty_overlay() -> SourceUncertaintyOverlay:
    positions = np.asarray(demo_head_scene().sources.positions_mm)
    elevation = positions[:, 2] / np.linalg.norm(positions, axis=1)
    mean = 5.0 + 9.0 * (1 - elevation) / 2
    return SourceUncertaintyOverlay(
        contract=OVERLAY_CONTRACT,
        head_id=DEMO_HEAD_ID,
        quantity="localisation_error",
        units="mm",
        statistic="mean",
        interval="confidence_interval",
        confidence_level=0.95,
        n_sources=len(mean),
        mean=[round(float(m), 3) for m in mean],
        lower=[round(float(0.65 * m), 3) for m in mean],
        upper=[round(float(1.6 * m), 3) for m in mean],
        origin="MOCK_FIXTURE",
        fixture=True,
        warnings=[
            "MOCK FIXTURE: M34 localisation-error results do not exist yet.",
            "Values are deterministic placeholders with no scientific meaning.",
        ],
    )


def _require_demo(head_id: str) -> None:
    if head_id != DEMO_HEAD_ID:
        raise HTTPException(
            404,
            "Only the synthetic demo head is served here; private anatomy stays on the "
            "opt-in loopback-only M32 viewer",
        )


def router() -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/head-scenes", response_model=list[HeadSceneSummary])
    def head_scenes() -> list[HeadSceneSummary]:
        scene = demo_head_scene()
        return [
            HeadSceneSummary(
                head_id=scene.head_id,
                label=scene.label,
                synthetic=scene.synthetic,
                readiness=scene.readiness,
            )
        ]

    @routes.get("/head-scenes/{head_id}", response_model=HeadScene)
    def head_scene(head_id: str) -> HeadScene:
        _require_demo(head_id)
        return demo_head_scene()

    @routes.get("/head-scenes/{head_id}/uncertainty", response_model=SourceUncertaintyOverlay)
    def head_uncertainty(head_id: str) -> SourceUncertaintyOverlay:
        _require_demo(head_id)
        return demo_uncertainty_overlay()

    return routes
