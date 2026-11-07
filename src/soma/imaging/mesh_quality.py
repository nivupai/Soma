"""Topology, winding and bounded triangle geometry checks in metres."""

from typing import Any

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from soma.imaging.surfaces import Mesh


def _point_triangle(p: Any, tri: Any) -> Any:
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac, ap = b - a, c - a, p - a
    normal = np.cross(ab, ac)
    n2 = np.sum(normal * normal, axis=1)
    projection = p - (np.sum(ap * normal, axis=1) / np.maximum(n2, 1e-40))[:, None] * normal
    v = projection - a
    d00, d01, d11 = np.sum(ab * ab, axis=1), np.sum(ab * ac, axis=1), np.sum(ac * ac, axis=1)
    d20, d21 = np.sum(v * ab, axis=1), np.sum(v * ac, axis=1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-40)
    u, w = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
    inside = (u >= -1e-10) & (w >= -1e-10) & (u + w <= 1 + 1e-10)
    distances = []
    for x, y in ((a, b), (b, c), (c, a)):
        edge = y - x
        t = np.clip(
            np.sum((p - x) * edge, axis=1) / np.maximum(np.sum(edge * edge, axis=1), 1e-40), 0, 1
        )
        distances.append(np.linalg.norm(p - x - t[:, None] * edge, axis=1))
    plane = np.abs(np.sum(ap * normal, axis=1)) / np.sqrt(np.maximum(n2, 1e-40))
    return np.where(inside, plane, np.min(distances, axis=0))


def _segment_distance(p: Any, q: Any, r: Any, s: Any) -> Any:
    u, v, w = q - p, s - r, p - r
    a, b, c = np.sum(u * u, axis=1), np.sum(u * v, axis=1), np.sum(v * v, axis=1)
    d, e = np.sum(u * w, axis=1), np.sum(v * w, axis=1)
    denominator = a * c - b * b
    parallel = denominator <= 1e-12 * a * c
    t = np.where(parallel, 0, np.clip((b * e - c * d) / np.maximum(denominator, 1e-40), 0, 1))
    z = (b * t + e) / np.maximum(c, 1e-40)
    t = np.where(z < 0, np.clip(-d / np.maximum(a, 1e-40), 0, 1), t)
    t = np.where(z > 1, np.clip((b - d) / np.maximum(a, 1e-40), 0, 1), t)
    z = np.clip(z, 0, 1)
    return np.linalg.norm(w + t[:, None] * u - z[:, None] * v, axis=1)


def triangle_distances(a: Any, b: Any) -> Any:
    result = np.full(len(a), np.inf)
    for i in range(3):
        result = np.minimum(result, _point_triangle(a[:, i], b))
        result = np.minimum(result, _point_triangle(b[:, i], a))
        for j in range(3):
            result = np.minimum(
                result, _segment_distance(a[:, i], a[:, (i + 1) % 3], b[:, j], b[:, (j + 1) % 3])
            )
    # An edge can pierce a triangle interior without touching another edge.
    for first, second in ((a, b), (b, a)):
        normal = np.cross(second[:, 1] - second[:, 0], second[:, 2] - second[:, 0])
        for i in range(3):
            p, q = first[:, i], first[:, (i + 1) % 3]
            d0, d1 = (
                np.sum((p - second[:, 0]) * normal, axis=1),
                np.sum((q - second[:, 0]) * normal, axis=1),
            )
            denominator = d0 - d1
            t = np.divide(d0, denominator, out=np.zeros_like(d0), where=np.abs(denominator) > 1e-30)
            point = p + t[:, None] * (q - p)
            hit = (
                (np.abs(denominator) > 1e-30)
                & (t >= 0)
                & (t <= 1)
                & (_point_triangle(point, second) < 1e-10)
            )
            result[hit] = 0
    return result


def surface_separation(
    a: Mesh, b: Mesh, *, tolerance_m: float = 1e-8, same_surface: bool = False
) -> dict[str, Any]:
    if a.vertices.frame != b.vertices.frame or tolerance_m <= 0:
        raise ValueError("Compatible mesh frames and positive tolerance required")
    ta, tb = a.vertices.xyz[a.faces], b.vertices.xyz[b.faces]
    ca, cb = ta.mean(axis=1), tb.mean(axis=1)
    ra, rb = (
        np.linalg.norm(ta - ca[:, None], axis=2).max(axis=1),
        np.linalg.norm(tb - cb[:, None], axis=2).max(axis=1),
    )
    tree = cKDTree(cb)
    upper = (
        tolerance_m
        if same_surface
        else float(cKDTree(b.vertices.xyz).query(a.vertices.xyz)[0].min())
    )
    minimum = upper
    intersections, candidate_count = 0, 0
    for start in range(0, len(ta), 128):
        lists = tree.query_ball_point(
            ca[start : start + 128], ra[start : start + 128] + rb.max() + upper
        )
        left, right = [], []
        for local, candidates in enumerate(lists):
            i = start + local
            for j in candidates:
                if same_surface and (i >= j or np.intersect1d(a.faces[i], b.faces[j]).size):
                    continue
                left.append(i)
                right.append(j)
        for offset in range(0, len(left), 8192):
            distances = triangle_distances(
                ta[np.array(left[offset : offset + 8192], dtype=int)],
                tb[np.array(right[offset : offset + 8192], dtype=int)],
            )
            if len(distances):
                minimum = min(minimum, float(distances.min()))
                intersections += int(np.sum(distances <= tolerance_m))
        candidate_count += len(left)
    return {
        "minimum_triangle_distance_m": None if same_surface else minimum,
        "intersecting_or_touching_triangle_pairs": intersections,
        "candidate_pairs": candidate_count,
        "tolerance_m": tolerance_m,
        "method": "centroid-sphere conservative broad phase; exact triangle feature distances",
        "adjacent_triangles_excluded": same_surface,
    }


def _nonmanifold_vertices(faces: Any, n: int) -> int:
    links: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for a, b, c in faces:
        links[a].append((int(b), int(c)))
        links[b].append((int(c), int(a)))
        links[c].append((int(a), int(b)))
    invalid = 0
    for pairs in links:
        graph: dict[int, set[int]] = {}
        for a, b in pairs:
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
        if not graph or any(len(neighbors) != 2 for neighbors in graph.values()):
            invalid += 1
            continue
        visited: set[int] = set()
        stack = [next(iter(graph))]
        while stack:
            vertex = stack.pop()
            if vertex not in visited:
                visited.add(vertex)
                stack.extend(graph[vertex] - visited)
        invalid += len(visited) != len(graph)
    return invalid


def mesh_quality(mesh: Mesh, *, self_intersections: bool = True) -> dict[str, Any]:
    vertices, faces = mesh.vertices.xyz, mesh.faces
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(cross, axis=1) / 2
    edges_directed = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges, inverse, counts = np.unique(
        np.sort(edges_directed, axis=1), axis=0, return_inverse=True, return_counts=True
    )
    direction = np.where(edges_directed[:, 0] < edges_directed[:, 1], 1, -1)
    balance = np.bincount(inverse, weights=direction)
    graph = coo_matrix(
        (
            np.ones(2 * len(edges)),
            (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]]),
        ),
        shape=(len(vertices),) * 2,
    ).tocsr()
    components, _ = connected_components(graph, directed=False)
    duplicate_faces = len(faces) - len(np.unique(np.sort(faces, axis=1), axis=0))
    degenerate = int(np.sum(area < 1e-16))
    lengths2 = np.sum((tri - np.roll(tri, 1, axis=1)) ** 2, axis=2)
    quality = 4 * np.sqrt(3) * area / np.maximum(lengths2.sum(axis=1), 1e-30)
    signed = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)
    nonmanifold_vertices = _nonmanifold_vertices(faces, len(vertices))
    topological = not (
        nonmanifold_vertices
        or duplicate_faces
        or degenerate
        or np.any(counts != 2)
        or np.any(balance != 0)
        or components != 1
    )
    self_check = (
        surface_separation(mesh, mesh, same_surface=True)
        if self_intersections and topological
        else None
    )
    valid = bool(
        topological
        and signed > 0
        and self_check is not None
        and self_check["intersecting_or_touching_triangle_pairs"] == 0
    )
    return {
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "edge_count": len(edges),
        "degenerate_triangles": degenerate,
        "duplicate_faces": duplicate_faces,
        "boundary_edges": int(np.sum(counts == 1)),
        "nonmanifold_edges": int(np.sum(counts > 2)),
        "nonmanifold_vertices": nonmanifold_vertices,
        "inconsistent_oriented_edges": int(np.sum((counts == 2) & (balance != 0))),
        "connected_components": int(components),
        "euler_characteristic": len(vertices) - len(edges) + len(faces),
        "surface_area_m2": float(area.sum()),
        "signed_volume_m3": signed,
        "enclosed_volume_m3": signed if valid else None,
        "volume_reliable_under_checks": valid,
        "outward_global_winding": signed > 0,
        "triangle_quality_min": float(quality.min()),
        "triangle_quality_median": float(np.median(quality)),
        "triangle_quality": quality.tolist(),
        "self_intersection_check": self_check,
        "geometrically_valid_under_checks": valid,
        "scope": (
            "single connected boundary; nonadjacent intersections checked, "
            "adjacent face degeneracy and winding checked; not general solid certification"
        ),
    }


def contains(mesh: Mesh, points: Any) -> Any:
    """Generalized winding number (solid angle); closed consistently wound meshes only."""
    tri = mesh.vertices.xyz[mesh.faces]
    result = []
    for point in np.asarray(points):
        a, b, c = (tri[:, i] - point for i in range(3))
        la, lb, lc = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1), np.linalg.norm(c, axis=1)
        numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
        denominator = (
            la * lb * lc
            + np.sum(a * b, axis=1) * lc
            + np.sum(b * c, axis=1) * la
            + np.sum(c * a, axis=1) * lb
        )
        winding = np.sum(2 * np.arctan2(numerator, denominator)) / (4 * np.pi)
        result.append(abs(winding) > 0.5)
    return np.asarray(result, dtype=bool)


def nested_boundaries(meshes: list[Mesh], *, minimum_separation_m: float = 0.001) -> dict[str, Any]:
    if len(meshes) != 3 or minimum_separation_m <= 0:
        raise ValueError(
            "Require exactly three ordered candidate boundaries and positive separation"
        )
    quality = [mesh_quality(mesh) for mesh in meshes]
    if any(not q["geometrically_valid_under_checks"] for q in quality):
        return {
            "geometric_candidate": False,
            "quality": quality,
            "reason": "invalid boundary",
            "physiological_conductor_validated": False,
        }
    pairs = []
    for inner, outer in zip(meshes[:-1], meshes[1:], strict=True):
        separation = surface_separation(inner, outer)
        # With closed connected nonintersecting boundaries, a point of the inner
        # boundary establishes nesting. Check several extrema as a diagnostic.
        vertices = inner.vertices.xyz
        probes = vertices[
            np.unique(np.r_[np.argmin(vertices, axis=0), np.argmax(vertices, axis=0)])
        ]
        inside = bool(contains(outer, probes).all())
        pairs.append(
            {
                **separation,
                "extrema_inside": inside,
                "contained": inside and separation["intersecting_or_touching_triangle_pairs"] == 0,
            }
        )
    passed = all(
        p["contained"] and p["minimum_triangle_distance_m"] >= minimum_separation_m for p in pairs
    )
    return {
        "geometric_candidate": passed,
        "quality": quality,
        "pairs": pairs,
        "required_separation_m": minimum_separation_m,
        "physiological_conductor_validated": False,
        "interpretation": (
            "geometric checks only; masks are not validated anatomical conductivity interfaces"
        ),
    }
