import json
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.anatomy.cache import cached_object
from soma.anatomy.config import frozen_config
from soma.anatomy.contracts import IndividualModel
from soma.anatomy.sensitivity import central_differences, forward_difference, local_covariance
from soma.anatomy.surfaces import ConductorSurfaces, Readiness, distance_to_surface, tri_state
from soma.anatomy.synthetic import sphere_forward, sphere_surfaces, synthetic_info
from soma.geometry import Frame, Points, Transform
from soma.imaging.surfaces import Mesh


def test_three_state_readiness_no_silent_certification():
    assert tri_state({"a": True}) == Readiness.PASS
    assert tri_state({"a": True, "b": None}) == Readiness.INDETERMINATE
    assert tri_state({"a": False, "b": None}) == Readiness.FAIL
    surfaces = sphere_surfaces(1)
    q = surfaces.readiness(sensor_compatible=True)
    assert q["status"] == "INDETERMINATE"
    assert q["computational_readiness"] == "PASS"
    assert q["unsupported_required_checks"] == ["anatomical_evidence"]
    assert not q["clinical_certification"]


def test_nonmanifold_and_nesting_rejected():
    surfaces = sphere_surfaces(0)
    meshes = list(surfaces.meshes)
    meshes[0] = Mesh(meshes[0].vertices, np.vstack([meshes[0].faces, meshes[0].faces[0]]))
    invalid = ConductorSurfaces("fake", tuple(meshes), surfaces.native, {"source": "synthetic"})
    assert invalid.readiness(sensor_compatible=True)["status"] == "FAIL"
    wrongly_nested = ConductorSurfaces(
        "fake", tuple(reversed(surfaces.meshes)), surfaces.native, {"source": "synthetic"}
    )
    assert wrongly_nested.readiness(sensor_compatible=True)["status"] == "FAIL"


def test_exact_triangle_distance_not_vertex_distance():
    mesh = Mesh(
        Points(np.array([[0.0, 0, 0], [0.1, 0, 0], [0, 0.1, 0]]), Frame.MRI), np.array([[0, 1, 2]])
    )
    p = Points(np.array([[0.02, 0.02, 0.01]]), Frame.MRI)
    assert_allclose(distance_to_surface(p, mesh), 0.01, atol=1e-12)
    with pytest.raises(ValueError):
        distance_to_surface(Points(p.xyz, Frame.HEAD), mesh)


def test_subject_and_sensor_provenance_rejection():
    surfaces = sphere_surfaces(0)
    info = synthetic_info()
    t = Transform(Frame.HEAD, Frame.MRI, np.eye(4))
    with pytest.raises(ValueError, match="identity"):
        IndividualModel("a", "b", "a", surfaces, info, t, {"sensor_origin": "digitized_EEG"})
    with pytest.raises(ValueError, match="digitization"):
        IndividualModel(
            "synthetic-sphere",
            "synthetic-sphere",
            "synthetic-sphere",
            surfaces,
            info,
            t,
            {"sensor_origin": "headshape_substitution"},
        )
    model = IndividualModel(
        "synthetic-sphere",
        "synthetic-sphere",
        "synthetic-sphere",
        surfaces,
        info,
        t,
        {"sensor_origin": "digitized_EEG"},
    )
    assert model.receipt()["mode"] == "participant_matched"


def test_numerical_derivative_independent_cubic_and_covariance():
    derivatives, records = central_differences(lambda t: np.array([[t + t**3]]), [0.1, 0.05, 0.025])
    errors = [abs(d[0, 0] - 1) for d in derivatives]
    assert errors[1] < errors[0] / 3.9 and errors[2] < errors[1] / 3.9
    assert (
        records[-1]["relative_change_from_previous"] < records[1]["relative_change_from_previous"]
    )
    j = np.array([[1.0, 2], [0, 3]])
    c = np.diag([0.1, 0.2])
    expected = np.array([[0.9, 1.2], [1.2, 1.8]])
    assert_allclose(local_covariance(j, c), expected)
    with pytest.raises(ValueError):
        local_covariance(j, np.diag([-1.0, 1]))
    with pytest.raises(ValueError):
        central_differences(lambda h: np.ones((2, 2)), [0])


def test_physical_cache_fingerprints_and_corruption(tmp_path):
    def build():
        return {"x": 3}

    def read(p):
        return json.loads(p.read_text())

    def write(p, x):
        p.write_text(json.dumps(x))

    a, r = cached_object(tmp_path, "toy", {"sigma": 0.3}, ".jsondata", build, read, write)
    b, s = cached_object(tmp_path, "toy", {"sigma": 0.3}, ".jsondata", build, read, write)
    assert not r["hit"] and s["hit"] and a == b
    _, changed = cached_object(tmp_path, "toy", {"sigma": 0.6}, ".jsondata", build, read, write)
    assert r["cache_key"] != changed["cache_key"]
    Path(r["path"]).write_text("corrupted")
    with pytest.raises(ValueError, match="checksum"):
        cached_object(tmp_path, "toy", {"sigma": 0.3}, ".jsondata", build, read, write)


def test_frozen_protocol_compatibility_with_legacy_seal_reader():
    from soma.source.workflow import sealed_config

    config = frozen_config(Path("configs/individual-source.yaml"))
    assert config["anatomy"]["surface_origin"] == "distributed_MNE_sample_FLASH_via_symlinks"
    assert config["_original_surface_origin"] == "distributed_MNE_sample_watershed"
    assert sealed_config(Path("configs/source-uncertainty.yaml"))
    assert frozen_config(Path("configs/bem.yaml").resolve())


def test_independent_analytical_sphere_and_physical_conductivity():
    points = np.array([[-0.02, 0.01, 0.03], [0.02, 0.01, 0.025]])
    analytical, _ = sphere_forward(points, analytical=True)
    coarse, _ = sphere_forward(points, subdivisions=0)
    fine, _ = sphere_forward(points, subdivisions=1)
    assert np.linalg.norm(fine - analytical) < np.linalg.norm(coarse - analytical)
    changed, receipt = sphere_forward(points, subdivisions=1, conductivities=(0.3, 0.012, 0.3))
    assert forward_difference(fine, changed)["relative_frobenius"] > 0.05
    assert receipt["conductor"]["parameters"]["conductivities_scalp_skull_brain"] == [
        0.3,
        0.012,
        0.3,
    ]
    assert_allclose(fine.sum(axis=0), 0, atol=1e-11)
    assert fine.shape == (24, 6)


def test_spherical_source_recovery_and_seeded_uncertainty():
    from soma.source.inverse import Tikhonov
    from soma.source.resolution import spatial_metrics

    xyz = np.array([[-0.02, 0.01, 0.03], [0.02, 0.01, 0.025]])
    lead, _ = sphere_forward(xyz, analytical=True)
    scale = np.linalg.svd(lead, compute_uv=False)[0]
    truth = np.array([0.0, 0.0, 1e-8, 0.0, 0.0, 0.0])
    estimate = Tikhonov(lead / scale, 0).solve(lead @ truth / scale)
    assert_allclose(estimate, truth, atol=1e-18)
    metrics = spatial_metrics(np.linalg.norm(estimate.reshape(-1, 3), axis=1), 0, xyz)
    assert metrics["peak_euclidean_m"] == 0

    def uncertain(seed):
        offsets = np.random.default_rng(seed).normal(0, 0.0002, 12)
        results = []
        for offset in offsets:
            transform = np.eye(4)
            transform[0, 3] = offset
            changed, _ = sphere_forward(
                xyz, subdivisions=0, transform=Transform(Frame.HEAD, Frame.MRI, transform)
            )
            results.append(changed @ truth)
        return np.stack(results)

    assert_allclose(uncertain(42), uncertain(42), atol=0, rtol=0)
    assert np.linalg.norm(uncertain(42) - uncertain(43)) > 0
