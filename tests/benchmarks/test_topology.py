import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.benchmarks.surfaces import analytic_values, convergence_record, field
from soma.benchmarks.topology import adjacency, repair, topology
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh, isosurface


def tetra():
    rr = np.array([[1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]], dtype=float) * 0.001
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    return Mesh(Points(rr, Frame.RAS), faces)


def test_tetrahedron_exact_topology_and_adjacency():
    mesh = tetra()
    a = adjacency(mesh)
    q = topology(mesh)
    assert len(a["edges"]) == 6 and np.all(a["edge_incidence"] == 2)
    assert all(len(x) == 3 for x in a["vertex_neighbors"])
    assert all(len(x) == 3 for x in a["face_neighbors"])
    assert q["euler_used_vertices"] == 2 and q["genus"] == 0 and q["orientable"]


def test_torus_euler_and_genus_oracle():
    nu, nv = 24, 12
    u, v = np.meshgrid(
        np.arange(nu) * 2 * np.pi / nu, np.arange(nv) * 2 * np.pi / nv, indexing="ij"
    )
    xyz = np.stack(
        [
            (0.02 + 0.006 * np.cos(v)) * np.cos(u),
            (0.02 + 0.006 * np.cos(v)) * np.sin(u),
            0.006 * np.sin(v),
        ],
        axis=-1,
    ).reshape(-1, 3)
    faces = []
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j
            b = ((i + 1) % nu) * nv + j
            c = ((i + 1) % nu) * nv + (j + 1) % nv
            d = i * nv + (j + 1) % nv
            faces.extend([[a, b, c], [a, c, d]])
    q = topology(Mesh(Points(xyz, Frame.RAS), np.array(faces)))
    assert q["euler_used_vertices"] == 0 and q["genus"] == 1


def test_hole_detection_and_small_cap_geometry():
    base = tetra()
    broken = Mesh(base.vertices, base.faces[1:])
    q = topology(broken)
    assert q["boundary_loop_count"] == 1 and len(q["boundary_loops"][0]) == 3 and q["genus"] is None
    fixed, audit = repair(broken, max_area_fraction=0.5)
    assert audit["accepted"] and audit["anatomical_review_required"]
    assert audit["vertex_Hausdorff_displacement_m"] == 0
    assert topology(fixed)["genus"] == 0
    assert not audit["anatomically_validated"]


def test_conservative_repair_rejects_large_area_change():
    base = tetra()
    broken = Mesh(base.vertices, base.faces[1:])
    returned, audit = repair(broken)
    assert not audit["accepted"] and audit["returned_original"]
    assert returned is broken


def test_duplicates_and_orientation_repairs_do_not_move_geometry():
    base = tetra()
    faces = np.vstack([base.faces, base.faces[0], [0, 0, 1]])
    faces[1] = faces[1, ::-1]
    dirty = Mesh(base.vertices, faces)
    fixed, audit = repair(dirty, max_area_fraction=0.3)
    assert audit["accepted"] and topology(fixed)["genus"] == 0
    assert_allclose(audit["vertex_Hausdorff_displacement_m"], 0)
    duplicated = Mesh(
        Points(np.vstack([base.vertices.xyz, base.vertices.xyz[0]]), Frame.RAS),
        np.where(base.faces == 0, 4, base.faces),
    )
    fixed, audit = repair(duplicated)
    assert audit["accepted"] and len(fixed.vertices.xyz) == 4


def test_nonmanifold_and_unassessed_geometry_have_no_genus():
    base = tetra()
    bad = Mesh(base.vertices, np.vstack([base.faces, base.faces[0]]))
    assert topology(bad)["genus"] is None
    assert topology(base, check_intersections=False)["genus"] is None
    with pytest.raises(ValueError):
        repair(base, max_vertex_m=-1)


def test_analytic_sphere_scalar_convergence_independent_formula():
    errors = []
    for step in [4.0, 2.0]:
        mesh = isosurface(field("sphere", step), level=0)
        record = convergence_record(mesh, "sphere", step, "scalar", 20000)
        errors.append(abs(record["algebraic_volume_relative_error"]))
        assert record["topology"]["euler_used_vertices"] == 2
    assert errors[1] < errors[0]
    assert_allclose(analytic_values("sphere")["area_m2"], 4 * np.pi * 0.03**2)
    assert_allclose(
        analytic_values("ellipsoid")["volume_m3"], 4 * np.pi * 0.035 * 0.025 * 0.018 / 3
    )
    assert_allclose(
        analytic_values("asymmetric", 64)["area_m2"],
        analytic_values("asymmetric", 128)["area_m2"],
        rtol=1e-10,
    )


def test_true_intersection_fixture_is_rejected_without_shape_repair():
    from soma.benchmarks.surfaces import repair_cases

    mesh = repair_cases()["self_intersection"]
    assert not topology(mesh)["geometrically_valid_under_checks"]
    returned, audit = repair(mesh)
    assert not audit["accepted"] and returned is mesh


def test_nonorientable_mobius_strip_has_no_genus():
    nu, nv = 20, 4
    points = []
    for i in range(nu):
        u = 2 * np.pi * i / nu
        for v in np.linspace(-0.003, 0.003, nv):
            points.append(
                [
                    (0.02 + v * np.cos(u / 2)) * np.cos(u),
                    (0.02 + v * np.cos(u / 2)) * np.sin(u),
                    v * np.sin(u / 2),
                ]
            )
    faces = []
    for i in range(nu):
        for j in range(nv - 1):
            a = i * nv + j
            b = i * nv + j + 1
            c = (i + 1) * nv + j + 1 if i < nu - 1 else nv - 2 - j
            d = (i + 1) * nv + j if i < nu - 1 else nv - 1 - j
            faces.extend([[a, b, c], [a, c, d]])
    mesh = Mesh(Points(np.array(points), Frame.RAS), np.array(faces))
    q = topology(mesh)
    assert not q["orientable"] and q["genus"] is None
