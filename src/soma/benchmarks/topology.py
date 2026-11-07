"""Explicit mesh incidence, orientability and conservative audited repairs."""

from collections import defaultdict, deque
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from soma.geometry import Points
from soma.imaging.mesh_quality import mesh_quality
from soma.imaging.surfaces import Mesh


def adjacency(mesh: Mesh) -> dict[str, Any]:
    incidence: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    vertices: list[set[int]] = [set() for _ in mesh.vertices.xyz]
    for i, face in enumerate(mesh.faces):
        for a, b in zip(face, np.roll(face, -1), strict=True):
            a, b = int(a), int(b)
            edge = (min(a, b), max(a, b))
            incidence[edge].append((i, 1 if a < b else -1))
            vertices[a].add(b)
            vertices[b].add(a)
    face_neighbors: list[list[int]] = [[] for _ in mesh.faces]
    constraints: list[list[tuple[int, int]]] = [[] for _ in mesh.faces]
    for members in incidence.values():
        if len(members) == 2:
            (a, da), (b, db) = members
            face_neighbors[a].append(b)
            face_neighbors[b].append(a)
            constraints[a].append((b, -da * db))
            constraints[b].append((a, -da * db))
    signs = np.zeros(len(mesh.faces), dtype=int)
    components = np.full(len(mesh.faces), -1, dtype=int)
    orientable = True
    count = 0
    for seed in range(len(signs)):
        if signs[seed]:
            continue
        signs[seed] = 1
        queue = deque([seed])
        components[seed] = count
        while queue:
            current = queue.popleft()
            for neighbor, relation in constraints[current]:
                expected = signs[current] * relation
                if signs[neighbor] and signs[neighbor] != expected:
                    orientable = False
                if not signs[neighbor]:
                    signs[neighbor] = expected
                    components[neighbor] = count
                    queue.append(neighbor)
        count += 1
    boundary = defaultdict(set)
    for (a, b), members in incidence.items():
        if len(members) == 1:
            boundary[a].add(b)
            boundary[b].add(a)
    loops = []
    remaining = set(boundary)
    branched = any(len(v) != 2 for v in boundary.values())
    while remaining:
        seed = min(remaining)
        component = set()
        stack = [seed]
        while stack:
            i = stack.pop()
            if i in component:
                continue
            component.add(i)
            stack.extend(boundary[i] - component)
        remaining -= component
        if any(len(boundary[v]) != 2 for v in component):
            continue
        loop = [seed]
        previous = -1
        current = seed
        while True:
            candidates = sorted(boundary[current] - {previous})
            nxt = candidates[0]
            if nxt == seed:
                break
            if nxt in loop:
                branched = True
                break
            loop.append(nxt)
            previous, current = current, nxt
        loops.append(loop)
    return {
        "edges": np.array(list(incidence), dtype=int),
        "edge_incidence": np.array([len(x) for x in incidence.values()]),
        "face_neighbors": face_neighbors,
        "vertex_neighbors": [sorted(v) for v in vertices],
        "face_components": components,
        "component_count": count,
        "orientation_signs": signs,
        "orientable": orientable,
        "boundary_loops": loops,
        "branched_boundary": branched,
    }


def topology(mesh: Mesh, *, check_intersections: bool = True) -> dict[str, Any]:
    adj = adjacency(mesh)
    q = mesh_quality(mesh, self_intersections=check_intersections)
    used = len(np.unique(mesh.faces))
    chi = used - len(adj["edges"]) + len(mesh.faces)
    suitable = (
        adj["orientable"]
        and adj["component_count"] == 1
        and q["geometrically_valid_under_checks"]
        and q["boundary_edges"] == 0
        and used == len(mesh.vertices.xyz)
    )
    genus = (2 - chi) // 2 if suitable and (2 - chi) % 2 == 0 and chi <= 2 else None
    return {
        **{k: v for k, v in q.items() if k != "triangle_quality"},
        "used_vertices": used,
        "euler_used_vertices": chi,
        "orientable": adj["orientable"],
        "face_components": adj["component_count"],
        "boundary_loop_count": len(adj["boundary_loops"]),
        "boundary_loops": adj["boundary_loops"],
        "branched_boundary": adj["branched_boundary"],
        "genus": genus,
        "genus_supported": genus is not None,
        "intersection_assessed": q["self_intersection_check"] is not None,
    }


def repair(
    mesh: Mesh,
    *,
    max_vertex_m: float = 0.00025,
    max_area_fraction: float = 0.01,
    max_hole_perimeter_m: float = 0.02,
    max_hole_area_m2: float = 0.00002,
) -> tuple[Mesh, dict[str, Any]]:
    if any(
        not np.isfinite(x) or x < 0
        for x in (max_vertex_m, max_area_fraction, max_hole_perimeter_m, max_hole_area_m2)
    ):
        raise ValueError("Finite nonnegative physical repair limits required")
    before = topology(mesh)
    logs: list[dict[str, Any]] = []
    xyz = mesh.vertices.xyz
    unique, first, inverse = np.unique(xyz, axis=0, return_index=True, return_inverse=True)
    faces = inverse[mesh.faces]
    logs.append(
        {"operation": "exact_duplicate_vertex_consolidation", "removed": len(xyz) - len(unique)}
    )
    tri = unique[faces]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    keep = area >= 1e-16
    logs.append({"operation": "degenerate_face_removal", "removed": int((~keep).sum())})
    faces = faces[keep]
    if len(faces) == 0:
        return mesh, {
            "accepted": False,
            "reason": "No usable triangles",
            "before": before,
            "operations": logs,
        }
    _, ids = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
    logs.append({"operation": "duplicate_face_removal", "removed": len(faces) - len(ids)})
    faces = faces[np.sort(ids)]
    used = np.unique(faces)
    remap = np.full(len(unique), -1, dtype=int)
    remap[used] = np.arange(len(used))
    faces = remap[faces]
    unique = unique[used]
    candidate = Mesh(Points(unique, mesh.vertices.frame), faces, mesh.metadata)
    adj = adjacency(candidate)
    caps = []
    unsupported = False
    for loop in adj["boundary_loops"]:
        coords = unique[loop]
        perimeter = float(np.linalg.norm(coords - np.roll(coords, 1, axis=0), axis=1).sum())
        cap_area = (
            float(np.linalg.norm(np.cross(coords[1] - coords[0], coords[2] - coords[0])) / 2)
            if len(loop) == 3
            else None
        )
        allowed = (
            len(loop) == 3
            and perimeter <= max_hole_perimeter_m
            and cap_area is not None
            and cap_area <= max_hole_area_m2
        )
        logs.append(
            {
                "operation": "small_triangular_hole",
                "vertices": loop,
                "perimeter_m": perimeter,
                "area_m2": cap_area,
                "supported": allowed,
            }
        )
        if allowed:
            caps.append(loop)
        else:
            unsupported = True
    if caps:
        faces = np.vstack([faces, np.array(caps, dtype=int)])
    candidate = Mesh(Points(unique, mesh.vertices.frame), faces, mesh.metadata)
    adj = adjacency(candidate)
    if adj["orientable"]:
        faces = faces.copy()
        flips = adj["orientation_signs"] < 0
        faces[flips] = faces[flips][:, [0, 2, 1]]
        for component in np.unique(adj["face_components"]):
            indices = adj["face_components"] == component
            tri = unique[faces[indices]]
            signed = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6
            if signed < 0:
                faces[indices] = faces[indices][:, [0, 2, 1]]
        logs.append({"operation": "consistent_outward_orientation", "BFS_flips": int(flips.sum())})
    candidate = Mesh(
        Points(unique, mesh.vertices.frame), faces, {**mesh.metadata, "repair_operations": logs}
    )
    after = topology(candidate)
    old = mesh.vertices.xyz[np.unique(mesh.faces)]
    displacement = max(
        float(cKDTree(unique).query(old)[0].max()), float(cKDTree(old).query(unique)[0].max())
    )
    area_change = after["surface_area_m2"] - before["surface_area_m2"]
    area_fraction = (
        abs(area_change) / before["surface_area_m2"] if before["surface_area_m2"] else float("inf")
    )
    accepted = bool(
        after["geometrically_valid_under_checks"]
        and displacement <= max_vertex_m
        and area_fraction <= max_area_fraction
        and not unsupported
    )
    result = {
        "accepted": accepted,
        "reason": "scoped computational repair accepted"
        if accepted
        else "defect unsupported, geometry failed or change exceeded limits",
        "before": before,
        "after_candidate": after,
        "vertex_Hausdorff_displacement_m": displacement,
        "area_change_m2": area_change,
        "relative_area_change": area_fraction if np.isfinite(area_fraction) else None,
        "valid_volume_change_m3": after["enclosed_volume_m3"] - before["enclosed_volume_m3"]
        if after["enclosed_volume_m3"] is not None and before["enclosed_volume_m3"] is not None
        else None,
        "operations": logs,
        "anatomical_review_required": bool(caps),
        "anatomically_validated": False,
        "returned_original": not accepted,
        "new_patch_area_m2": float(
            sum(
                x["area_m2"]
                for x in logs
                if x["operation"] == "small_triangular_hole" and x["supported"]
            )
        ),
    }
    return candidate if accepted else mesh, result
