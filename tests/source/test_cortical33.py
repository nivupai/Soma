"""Cortical midsurface source space: synthetic oracles and an MNE sample replay."""

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import ConvexHull

from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains
from soma.imaging.surfaces import Mesh
from soma.source.cortical import (
    UNLABELLED,
    HemisphereSurfaces,
    build_cortical_source_space,
    parse_spacing,
    subdivided_sphere,
    vertex_normals,
)


def sphere_mesh(spacing="ico3"):
    v = subdivided_sphere(spacing)
    f = np.asarray(ConvexHull(v).simplices, np.int64)
    tri = v[f]
    outward = np.einsum(
        "ij,ij->i", np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), tri[:, 0]
    )
    f[outward < 0] = f[outward < 0][:, [0, 2, 1]]
    return v, f


def skull(radius=0.07, shift=(0.0, 0.0, 0.0)):
    v, f = sphere_mesh("ico3")
    return Mesh(Points(v * radius + np.asarray(shift), Frame.MRI), f)


def hemisphere(hemi="lh", *, offset=0.0, white=0.05, pial=0.053):
    unit, f = sphere_mesh("ico4")
    labels = np.zeros(len(unit), np.int64)
    labels[unit[:, 0] < -0.8] = -1  # medial wall (unlabelled)
    labels[(unit[:, 0] > 0.85)] = 1  # named region excluded by default
    shift = np.array([offset, 0.0, 0.0])
    return HemisphereSurfaces(
        hemi,
        unit * white + shift,
        unit * pial + shift,
        unit * 3,
        f,
        labels,
        ("cortex", "corpuscallosum", "unknown"),
    )


def test_spacing_counts_match_mne_conventions():
    assert parse_spacing("ico4")[2] == len(subdivided_sphere("ico4")) == 2562
    assert parse_spacing("oct6")[2] == len(subdivided_sphere("oct6")) == 4098
    assert len(subdivided_sphere("ico5")) == 10242
    assert np.allclose(np.linalg.norm(subdivided_sphere("oct3"), axis=1), 1, atol=1e-12)
    for bad in ["ico", "oct0", "ico8", "spacing5", "ICO4"]:
        with pytest.raises(ValueError):
            parse_spacing(bad)


def test_synthetic_coverage_weights_normals_and_named_exclusions():
    h = hemisphere()
    space = build_cortical_source_space([h], skull(), spacing="ico3")
    r = space.report
    mid = h.midsurface_m
    unit = h.sphere
    medial, callosum = unit[:, 0] < -0.8, unit[:, 0] > 0.85
    from soma.source.priors import vertex_areas

    area = vertex_areas(mid, h.faces)
    eligible_area = area[~(medial | callosum)].sum()
    # No containment/orientation loss: retained area equals the label-eligible area.
    assert np.isclose(space.total_area_m2, eligible_area, rtol=1e-12, atol=0)
    assert np.isclose(r["coverage"]["area_fraction_of_eligible_cortex"], 1, rtol=1e-12)
    assert np.isclose(
        r["coverage"]["area_fraction_of_midsurface"], eligible_area / area.sum(), rtol=1e-12
    )
    assert r["coverage"]["vertex_fraction_retained"] == len(space.positions_m) / len(mid)
    rows = {(e["reason"], e["label"]): e for e in r["exclusions"]}
    assert rows[("anatomical_label", UNLABELLED)]["full_resolution_vertices"] == medial.sum()
    assert rows[("anatomical_label", "corpuscallosum")]["full_resolution_vertices"] == (
        callosum.sum()
    )
    assert rows[("anatomical_label", "unknown")]["full_resolution_vertices"] == 0
    assert rows[("outside_inner_skull", None)]["candidate_sources"] == 0
    retained = np.concatenate(space.vertices)
    assert not (medial | callosum)[retained].any()
    # Radial outward normals on a sphere agree with the white->pial direction.
    radial = space.positions_m / np.linalg.norm(space.positions_m, axis=1)[:, None]
    assert np.einsum("ij,ij->i", space.normals, radial).min() > 0.999
    assert r["orientation"]["outward_fraction_of_defined"] == 1
    assert contains(skull(), space.positions_m).all()
    assert space.source_ids[0].startswith("lh:")
    json.dumps(r, allow_nan=False)


def test_containment_failures_are_excluded_with_reasons_not_redistributed():
    h = hemisphere()
    shifted = skull(0.06, (0.03, 0.0, 0.0))
    space = build_cortical_source_space([h], shifted, spacing="ico3")
    r = space.report
    outside = next(e for e in r["exclusions"] if e["reason"] == "outside_inner_skull")
    assert outside["candidate_sources"] > 0 and outside["area_mm2"] > 0
    assert sum(outside["candidate_regions"].values()) == outside["candidate_sources"]
    assert contains(shifted, space.positions_m).all()
    assert r["containment"]["retained_sources_inside"] == len(space.positions_m)
    lost = sum(e["area_mm2"] for e in r["exclusions"] if e["reason"] != "anatomical_label")
    from soma.source.priors import vertex_areas

    area = vertex_areas(h.midsurface_m, h.faces)
    eligible = area[h.labels == 0].sum() * 1e6
    # Excluded patches are accounted for, never silently reassigned to neighbours.
    assert np.isclose(space.total_area_m2 * 1e6 + lost, eligible, rtol=1e-12, atol=0)
    assert r["coverage"]["area_fraction_of_eligible_cortex"] < 1
    strict = build_cortical_source_space([h], shifted, spacing="ico3", minimum_margin_m=0.005)
    margin = next(
        e for e in strict.report["exclusions"] if e["reason"] == "inner_skull_margin_below_minimum"
    )
    assert margin["candidate_sources"] > 0
    assert strict.report["containment"]["retained_margin_min_mm"] >= 5
    assert len(strict.positions_m) < len(space.positions_m)


def test_orientation_disagreement_is_excluded_and_inward_winding_refused():
    h = hemisphere()
    flip = h.sphere[:, 2] > 0.6
    white, pial = h.white_m.copy(), h.pial_m.copy()
    white[flip], pial[flip] = h.pial_m[flip], h.white_m[flip]
    bad = HemisphereSurfaces("lh", white, pial, h.sphere, h.faces, h.labels, h.label_names)
    space = build_cortical_source_space([bad], skull(), spacing="ico3")
    row = next(
        e for e in space.report["exclusions"] if e["reason"] == "normal_opposes_white_to_pial"
    )
    assert row["candidate_sources"] > 0
    assert not flip[np.concatenate(space.vertices)].any()
    assert space.report["orientation"]["retained_cosine_min"] > 0
    inward = HemisphereSurfaces(
        "lh", h.white_m, h.pial_m, h.sphere, h.faces[:, [0, 2, 1]], h.labels, h.label_names
    )
    with pytest.raises(ValueError, match="winding"):
        build_cortical_source_space([inward], skull(), spacing="ico3")
    thin = HemisphereSurfaces(
        "lh", h.white_m, h.white_m, h.sphere, h.faces, h.labels, h.label_names
    )
    with pytest.raises(ValueError, match="No cortical source"):
        build_cortical_source_space([thin], skull(), spacing="ico3")


def test_two_hemispheres_ids_identity_and_immutability():
    lh, rh = hemisphere("lh", offset=-0.006), hemisphere("rh", offset=0.006)
    space = build_cortical_source_space([lh, rh], skull(0.09), spacing="ico2")
    assert set(space.report["hemispheres"]) == {"lh", "rh"}
    assert len(set(space.source_ids)) == len(space.source_ids)
    other = build_cortical_source_space([lh, rh], skull(0.09), spacing="ico3")
    assert space.identity != other.identity
    with pytest.raises(ValueError):
        space.positions_m[0, 0] = 1.0
    with pytest.raises(ValueError):
        build_cortical_source_space([lh, lh], skull(0.09), spacing="ico2")


@pytest.mark.parametrize("fault", ["mm", "topology", "labels", "hemi", "frame", "open_skull"])
def test_invalid_inputs_refused(fault):
    h = hemisphere()
    with pytest.raises(ValueError):
        if fault == "mm":
            HemisphereSurfaces(
                "lh", h.white_m * 1000, h.pial_m * 1000, h.sphere, h.faces, h.labels, h.label_names
            )
        elif fault == "topology":
            HemisphereSurfaces(
                "lh", h.white_m, h.pial_m[:-1], h.sphere, h.faces, h.labels, h.label_names
            )
        elif fault == "labels":
            HemisphereSurfaces(
                "lh", h.white_m, h.pial_m, h.sphere, h.faces, h.labels + 5, h.label_names
            )
        elif fault == "hemi":
            HemisphereSurfaces(
                "both", h.white_m, h.pial_m, h.sphere, h.faces, h.labels, h.label_names
            )
        elif fault == "frame":
            s = skull()
            build_cortical_source_space([h], Mesh(Points(s.vertices.xyz, Frame.HEAD), s.faces))
        else:
            s = skull()
            build_cortical_source_space([h], Mesh(s.vertices, s.faces[1:]), spacing="ico2")


def test_vertex_normals_follow_winding():
    v, f = sphere_mesh("ico2")
    assert np.allclose(vertex_normals(v, f), v, atol=0.05)
    assert np.allclose(vertex_normals(v, f[:, [0, 2, 1]]), -v, atol=0.05)


def test_freesurfer_roundtrip(tmp_path):
    import nibabel.freesurfer as fs

    h = hemisphere()
    (tmp_path / "surf").mkdir()
    (tmp_path / "label").mkdir()
    for name, value in [("white", h.white_m), ("pial", h.pial_m), ("sphere", h.sphere * 100)]:
        fs.write_geometry(
            str(tmp_path / f"surf/lh.{name}"), value * (1000 if name != "sphere" else 1), h.faces
        )
    ctab = np.array([[10 * i + 10, 20, 30, 0, 0] for i in range(3)], np.int32)
    fs.write_annot(
        str(tmp_path / "label/lh.aparc.annot"), h.labels, ctab, list(h.label_names), fill_ctab=True
    )
    loaded = HemisphereSurfaces.from_freesurfer(tmp_path, "lh")
    assert np.allclose(loaded.white_m, h.white_m, atol=1e-6)
    assert loaded.label_names == h.label_names
    assert np.array_equal(loaded.labels, h.labels)


def test_volumetric_domain_implementation_unchanged():
    recorded = json.loads(Path("src/soma/resources/mri-head-models-example-v32.json").read_text())
    digest = hashlib.sha256(Path("src/soma/source/domains.py").read_bytes()).hexdigest()
    assert recorded["implementation_sha256"]["src/soma/source/domains.py"] == digest


@pytest.mark.integration
def test_mne_sample_cortical_source_space_replay():
    import mne

    from soma.anatomy.surfaces import ConductorSurfaces

    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    subject = root / "mne-sample/MNE-sample-data/subjects/sample"
    bem = subject / "bem/sample-5120-5120-5120-bem.fif"
    if not (bem.is_file() and (subject / "surf/lh.pial").is_file()):
        pytest.skip("Explicitly cached MNE sample anatomy required; test never fetches")
    hemis = [HemisphereSurfaces.from_freesurfer(subject, h) for h in ("lh", "rh")]
    inner = ConductorSurfaces.from_mne(
        "sample", mne.read_bem_surfaces(bem, verbose=False), {"source": "MNE sample BEM"}
    ).meshes[0]
    space = build_cortical_source_space(hemis, inner, spacing="oct6")
    r = space.report
    assert r["coverage"]["area_fraction_of_midsurface"] > 0.9
    assert r["coverage"]["area_fraction_of_eligible_cortex"] > 0.99
    assert contains(inner, space.positions_m).all()
    assert r["orientation"]["outward_fraction_of_defined"] > 0.999
    assert r["orientation"]["retained_cosine_min"] > 0
    labels = {(e["hemisphere"], e["label"]) for e in r["exclusions"] if e["label"]}
    assert {("lh", UNLABELLED), ("rh", UNLABELLED), ("lh", "unknown")} <= labels
    medial = [e for e in r["exclusions"] if e["label"] == UNLABELLED]
    assert [e["full_resolution_vertices"] for e in medial] == [8260, 8641]
    committed = json.loads(
        Path("experiments/milestone33/cortical-source-space-sample.json").read_text()
    )
    assert committed["counts"] == r["counts"]
    assert np.isclose(
        committed["coverage"]["area_fraction_of_midsurface"],
        r["coverage"]["area_fraction_of_midsurface"],
        rtol=1e-12,
    )
    assert committed["exclusions"] == r["exclusions"]
