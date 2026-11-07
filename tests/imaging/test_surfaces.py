import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.geometry import Frame, Points, Transform
from soma.imaging.bridge import AnatomicalModel
from soma.imaging.mesh_quality import (
    contains,
    mesh_quality,
    nested_boundaries,
    surface_separation,
    triangle_distances,
)
from soma.imaging.phantoms import sphere
from soma.imaging.segmentation import (
    agreement,
    components,
    process_mask,
    region_volumes,
    threshold_mask,
    validate_mask,
)
from soma.imaging.surfaces import Mesh, extract_surface, smooth
from soma.imaging.volumes import Volume


def tetra(scale=0.01, center=(0, 0, 0)):
    xyz = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]) * scale + center
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    return Mesh(Points(xyz, Frame.RAS), faces)


def test_tetra_analytic_mesh_and_winding():
    mesh = tetra()
    q = mesh_quality(mesh)
    assert q["euler_characteristic"] == 2
    assert q["edge_count"] == 6
    assert q["connected_components"] == 1
    assert q["boundary_edges"] == 0
    assert q["geometrically_valid_under_checks"]
    assert_allclose(q["enclosed_volume_m3"], 0.01**3 / 6, rtol=1e-12)
    assert_allclose(q["surface_area_m2"], (3 + np.sqrt(3)) * 0.01**2 / 2)
    assert contains(mesh, [[0.001, 0.001, 0.001], [0.02, 0, 0]]).tolist() == [True, False]
    assert not mesh_quality(Mesh(mesh.vertices, mesh.faces[:, [0, 2, 1]]))[
        "volume_reliable_under_checks"
    ]


@pytest.mark.parametrize("mode", ["open", "duplicate", "degenerate", "inconsistent", "nonmanifold"])
def test_invalid_meshes(mode):
    mesh = tetra()
    f = mesh.faces.copy()
    if mode == "open":
        f = f[:-1]
    elif mode == "duplicate":
        f = np.vstack([f, f[0]])
    elif mode == "degenerate":
        f = np.vstack([f, [0, 0, 1]])
    elif mode == "inconsistent":
        f[0] = f[0, [0, 2, 1]]
    else:
        f = np.vstack([f, [0, 1, 2]])
    q = mesh_quality(Mesh(mesh.vertices, f))
    assert not q["geometrically_valid_under_checks"]
    assert q["enclosed_volume_m3"] is None


def test_triangle_intersection_and_separation_independent():
    a = np.array([[[0.0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    b = np.array([[[0.2, 0.2, -1], [0.2, 0.2, 1], [0.8, 0.2, 1]]])
    assert_allclose(triangle_distances(a, b), 0, atol=1e-14)
    assert_allclose(triangle_distances(a, a + [0, 0, 2]), 2)
    assert_allclose(triangle_distances(a, a + [2, 0, 0]), 1)
    mesh = tetra()
    other = tetra(center=(0.02, 0, 0))
    assert_allclose(
        surface_separation(mesh, other)["minimum_triangle_distance_m"], 0.01, atol=1e-12
    )


def test_marching_cubes_physical_reflection_and_smoothing():
    mask = sphere(0.018, 0.006)
    mesh = extract_surface(mask)
    q = mesh_quality(mesh)
    assert q["geometrically_valid_under_checks"] and q["euler_characteristic"] == 2
    reflected = mask.affine_m.copy()
    reflected[0] *= -1
    other = extract_surface(Volume(mask.array(), reflected, "labels"))
    assert mesh_quality(other)["signed_volume_m3"] > 0
    assert_allclose(np.abs(other.vertices.xyz).max(axis=0), np.abs(mesh.vertices.xyz).max(axis=0))
    result = smooth(mesh, iterations=1, step=0.1)
    assert np.array_equal(result.faces, mesh.faces)
    assert result.metadata["smoothing"]["max_vertex_change_m"] > 0
    assert (
        result.metadata["smoothing"]["euler_before"] == result.metadata["smoothing"]["euler_after"]
    )
    touching = np.ones(mask.shape, dtype=np.uint8)
    with pytest.raises(ValueError):
        extract_surface(Volume(touching, mask.affine_m, "labels"))


def test_labels_overlap_components_and_geometry():
    a = np.zeros((6, 6, 6), dtype=np.uint8)
    a[1:3, 1:3, 1:3] = 1
    a[4, 4, 4] = 1
    affine = np.diag([0.001, 0.002, 0.003, 1])
    v = Volume(a, affine, "labels")
    b = a.copy()
    b[4, 4, 4] = 0
    w = Volume(b, affine, "labels")
    assert agreement(v, w)["dice"] == pytest.approx(16 / 17)
    assert agreement(v, w)["jaccard"] == pytest.approx(8 / 9)
    assert region_volumes(v)[1] == pytest.approx(9 * 6e-9)
    _, info = components(v)
    assert info["count"] == 2
    cleaned = process_mask(v, largest_component=True)
    assert cleaned.array().sum() == 8
    validate_mask(v, Volume(a, affine))
    bad = affine.copy()
    bad[0, 3] = 0.01
    with pytest.raises(ValueError):
        agreement(v, Volume(a, bad, "labels"))
    baseline = threshold_mask(Volume(a.astype(float), affine), threshold=0.5)
    assert agreement(v, baseline)["dice"] == 1


def test_nested_synthetic_and_source_bridge():
    masks = [sphere(r, 0.008) for r in [0.016, 0.032, 0.048]]
    meshes = tuple(extract_surface(v) for v in masks)
    diagnostics = nested_boundaries(list(meshes), minimum_separation_m=0.003)
    assert diagnostics["geometric_candidate"]
    assert not diagnostics["physiological_conductor_validated"]
    model = AnatomicalModel(
        "synthetic-only",
        masks[0],
        meshes,
        Transform(Frame.RAS, Frame.MRI, np.eye(4)),
        "Synthetic coincident RAS/tkRAS by construction",
    )
    surfaces, report = model.mne_candidates()
    assert [s["id"] for s in surfaces] == [1, 3, 4]
    assert surfaces[0]["coord_frame"] == 5
    assert not report["individual_forward_validated"]
    alignment = model.validate_sensor_alignment(
        subject="synthetic-only",
        head_to_mri=Transform(Frame.HEAD, Frame.MRI, np.eye(4)),
        provenance="synthetic known alignment",
    )
    assert_allclose(alignment["head_to_NIfTI_RAS_m"], np.eye(4))
    assert report["MRI_provenance"]["origin"] == "synthetic_sphere"
    assert_allclose(report["NIfTI_RAS_to_MNE_MRI_m"], np.eye(4))
    with pytest.raises(ValueError):
        model.validate_sensor_alignment(
            subject="PhysioNet-S001",
            head_to_mri=Transform(Frame.HEAD, Frame.MRI, np.eye(4)),
            provenance="unrelated MRI",
        )
    assert not nested_boundaries(list(reversed(meshes)))["geometric_candidate"]


def test_scalar_sphere_converges_to_analytic_geometry():
    from soma.imaging.phantoms import analytic_sphere_field
    from soma.imaging.surfaces import isosurface

    errors = []
    for spacing in [0.006, 0.004, 0.003]:
        q = mesh_quality(isosurface(analytic_sphere_field(spacing), level=0))
        errors.append(
            [
                abs(q["surface_area_m2"] - 4 * np.pi * 0.03**2),
                abs(q["enclosed_volume_m3"] - 4 * np.pi / 3 * 0.03**3),
            ]
        )
    assert np.all(np.diff(np.array(errors), axis=0) < 0)


def test_nonmanifold_vertex_and_touching_candidates_rejected():
    a = tetra()
    # Two nondegenerate outward tetrahedra share only their origin vertex.
    # Their edge counts/winding are valid; only the vertex link exposes the defect.
    second_faces = a.faces[:, [0, 2, 1]].copy()
    second_faces[second_faces != 0] += 3
    vertices = np.vstack([a.vertices.xyz, -a.vertices.xyz[1:]])
    mesh = Mesh(Points(vertices, Frame.RAS), np.vstack([a.faces, second_faces]))
    q = mesh_quality(mesh)
    assert q["connected_components"] == 1
    assert q["degenerate_triangles"] == 0
    assert q["nonmanifold_edges"] == 0
    assert q["nonmanifold_vertices"] == 1
    assert q["enclosed_volume_m3"] is None
    pair = surface_separation(a, tetra(center=(0.002, 0.002, 0.002)))
    assert pair["intersecting_or_touching_triangle_pairs"] > 0


def test_label_mask_negative_inputs():
    from soma.imaging.segmentation import require_labels

    v = Volume(np.ones((3, 3, 3)), np.diag([0.001, 0.001, 0.001, 1]))
    with pytest.raises(ValueError):
        require_labels(v)
    with pytest.raises(ValueError):
        process_mask(Volume(np.full((3, 3, 3), 2, dtype=np.uint8), v.affine_m, "labels"))
    with pytest.raises(ValueError):
        threshold_mask(v)
