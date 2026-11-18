"""Independent mesher contracts and frozen source-grid geometry; synthetic only."""

import importlib
import time
from typing import Any

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from soma.anatomy.synthetic import sphere_mesh
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import validate
from soma.source.fem_reference import tetra_quality
from soma.source.nonspherical import boundary_points, head_parameters, meshes


def boundaries(head: int | None, level: int, independent: bool = False) -> list[Mesh]:
    if level not in (1, 2, 3):
        raise ValueError("Unplanned angular resolution")
    u, faces = sphere_mesh(level, 1.0)
    if independent:
        rotation = Rotation.from_rotvec(np.array([1.0, 2.0, 3.0]) / np.sqrt(14) * np.deg2rad(17))
        canonical, _ = sphere_mesh(1, 1.0)
        u = np.vstack([canonical[:32], rotation.apply(u)])
        _, indices = np.unique(np.round(u, 14), axis=0, return_index=True)
        u = u[np.sort(indices)]
        faces = ConvexHull(u).simplices.copy()
        tri = u[faces]
        reverse = (
            np.sum(
                np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]) * tri.mean(axis=1), axis=1
            )
            < 0
        )
        faces[reverse, :2] = faces[reverse, 1::-1]
    if head is not None and not independent:
        return meshes(head_parameters(head), level)
    return [
        Mesh(
            Points(
                u * r if head is None else boundary_points(head_parameters(head), i, u), Frame.MRI
            ),
            faces,
            {"synthetic": True},
        )
        for i, r in enumerate([0.081, 0.0828, 0.0873, 0.09])
    ]


def candidate_grid(spacing_mm: int) -> Points:
    if spacing_mm not in (30, 20, 15):
        raise ValueError("Unplanned source-grid spacing")
    axis = np.arange(-60, 60.001, spacing_mm) / 1000
    xyz = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    xyz = xyz[np.linalg.norm(xyz, axis=1) <= 0.065 + 1e-12]
    return Points(xyz, Frame.MRI)


def nearest_distances(grid: Any, truth: Any) -> Any:
    grid = np.asarray(grid, float)
    truth = np.asarray(truth, float)
    if (
        grid.ndim != 2
        or grid.shape[1] != 3
        or truth.ndim != 2
        or truth.shape[1] != 3
        or not len(grid)
        or not np.isfinite(grid).all()
        or not np.isfinite(truth).all()
        or max(np.max(np.abs(grid)), np.max(np.abs(truth))) > 0.1
    ):
        raise ValueError("MRI metre source arrays required")
    distances = np.linalg.norm(truth[:, None] - grid[None], axis=2)
    if np.any(distances.min(axis=1) < 1e-6):
        raise ValueError("Off-grid truth leaked into inverse candidates")
    return distances.min(axis=1) * 1000


def facet_signature(triangles: Any) -> list[Any]:
    return sorted(tuple(sorted(tuple(p) for p in tri)) for tri in np.asarray(triangles))


def audit_volume(
    vertices: Any, tetrahedra: Any, labels: Any, surfaces: list[Mesh]
) -> dict[str, Any]:
    q = tetra_quality(vertices, tetrahedra, labels)
    v = np.asarray(vertices)
    t = np.asarray(tetrahedra)
    labels = np.asarray(labels)
    fs = np.sort(
        np.concatenate([t[:, [0, 1, 2]], t[:, [0, 1, 3]], t[:, [0, 2, 3]], t[:, [1, 2, 3]]]), axis=1
    )
    lab = np.tile(labels, 4)
    order = np.lexsort(fs.T[::-1])
    fs = fs[order]
    lab = lab[order]
    unique, starts, counts = np.unique(fs, axis=0, return_index=True, return_counts=True)
    if np.any(counts > 2):
        raise ValueError("Nonmanifold tetrahedral facets")
    deviations = []
    previous = 0.0
    volumes = []
    x = v[t]
    cell_volume = np.linalg.det(np.stack([x[:, j] - x[:, 0] for j in (1, 2, 3)], axis=2)) / 6
    for i, surface in enumerate(surfaces):
        if i == 3:
            actual = unique[counts == 1]
        else:
            actual = unique[
                [
                    index
                    for index in np.flatnonzero(counts == 2)
                    if set(lab[starts[index] : starts[index] + 2]) == {i, i + 1}
                ]
            ]
        if facet_signature(v[actual]) != facet_signature(surface.vertices.xyz[surface.faces]):
            raise ValueError("Mesher altered or mislabeled physical interface facets")
        # Vertex-coordinate correspondence is independently checked without quantized hashes.
        distance = np.linalg.norm(
            surface.vertices.xyz[:, None] - v[np.unique(actual)][None], axis=2
        ).min(axis=1)
        deviations.append(float(distance.max()))
        tri = surface.vertices.xyz[surface.faces]
        enclosed = float(np.sum(tri[:, 0] * np.cross(tri[:, 1], tri[:, 2])) / 6)
        expected = enclosed - previous
        actual_volume = float(cell_volume[labels == i].sum())
        if expected <= 0 or abs(actual_volume - expected) / expected > 1e-9:
            raise ValueError("Tissue volume/label mismatch")
        volumes.append(actual_volume)
        previous = enclosed
    if max(deviations) > 1e-12:
        raise ValueError("Boundary coordinate drift")
    q.update(
        interface_connectivity_verified=True,
        boundary_coordinate_max_m=max(deviations),
        tissue_volumes_m3=volumes,
    )
    return q


def gmsh_mesh(
    surfaces: list[Mesh], electrodes: Any, max_size_m: float
) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Call official Gmsh in its owning worker; preserve pre-existing discrete facets."""
    if max_size_m not in (0.025, 0.015, 0.009):
        raise ValueError("Unplanned volume size")
    validate(surfaces, np.zeros((1, 3)), electrodes, [0.33, 1.0, 0.004, 0.33])
    gmsh = importlib.import_module("gmsh")
    if gmsh.__version__ != "4.15.2":
        raise ValueError("Pinned external Gmsh4.15.2 required")
    started = time.perf_counter()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MeshOnlyEmpty", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMax", max_size_m)
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.001)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.option.setNumber("Mesh.RandomSeed", 30042)
        offset = 0
        entities = []
        for i, m in enumerate(surfaces):
            tag = gmsh.model.addDiscreteEntity(2, i + 1)
            entities.append(tag)
            tags = np.arange(offset + 1, offset + 1 + len(m.vertices.xyz))
            gmsh.model.mesh.addNodes(2, tag, tags, m.vertices.xyz.ravel())
            gmsh.model.mesh.addElementsByType(tag, 2, [], (m.faces + offset + 1).ravel())
            offset += len(tags)
        loops = [gmsh.model.geo.addSurfaceLoop([s]) for s in entities]
        volumes = [gmsh.model.geo.addVolume([loops[0]])] + [
            gmsh.model.geo.addVolume([loops[i], loops[i - 1]]) for i in range(1, 4)
        ]
        gmsh.model.geo.synchronize()
        for i, volume in enumerate(volumes):
            tag = gmsh.model.addPhysicalGroup(3, [volume], i + 1)
            gmsh.model.setPhysicalName(3, tag, ["brain", "CSF", "skull", "scalp"][i])
        gmsh.model.mesh.generate(3)
        nodes, xyz, _ = gmsh.model.mesh.getNodes()
        v = np.asarray(xyz).reshape(-1, 3)
        lookup = {int(n): i for i, n in enumerate(nodes)}
        t: list[Any] = []
        labels = []
        native_quality = []
        for i, volume in enumerate(volumes):
            kinds, tags, connectivity = gmsh.model.mesh.getElements(3, volume)
            for kind, ids, cell in zip(kinds, tags, connectivity, strict=True):
                if kind != 4:
                    raise ValueError("Only first-order tetrahedra supported")
                cells = np.array([lookup[int(n)] for n in cell]).reshape(-1, 4)
                t.extend(cells)
                labels.extend([i] * len(cells))
                native_quality.extend(gmsh.model.mesh.getElementQualities(ids, "minSICN"))
        cells = np.array(t, dtype=np.int64)
        tissues = np.array(labels, dtype=np.int64)
        q = audit_volume(v, cells, tissues, surfaces)
        q.update(
            mesher="Gmsh",
            mesher_version=gmsh.__version__,
            mesh_seconds=time.perf_counter() - started,
            max_size_m=max_size_m,
            native_minSICN=float(min(native_quality)),
            boundary_policy="MeshOnlyEmpty; imported discrete facets retained; no Soma extrusion",
        )
        return v, cells, tissues, q
    finally:
        gmsh.finalize()
