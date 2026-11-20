"""Independent MRI frame, evidence-level, domain and privacy regressions."""

import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from soma.anatomy.head_models import (
    COMPUTATIONAL_CHECKS,
    MRIFrameChain,
    classify_anatomy,
    require_forward_ready,
)
from soma.geometry import Frame, Transform
from soma.source.domains import SourceDomain
from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import PriorInverse, SourcePrior


def image_chain():
    affine = np.diag([1.0, 2.0, 3.0, 1.0])
    affine[:3, 3] = [10, 20, 30]
    image = nib.MGHImage(np.zeros((4, 6, 8), np.float32), affine)
    t = np.eye(4)
    t[:3, 3] = [0.01, -0.02, 0.03]
    return image, MRIFrameChain.from_mgh(image, Transform(Frame.HEAD, Frame.MRI, t))


def test_independent_tkregister_voxel_center_oracle():
    image, chain = image_chain()
    p = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]])
    # Independently derive tkregister RAS from dimensions/spacings, not inverse functions.
    expected = np.array([[2.0, -12.0, 6.0], [1.0, -3.0, 2.0]]) * 0.001
    assert np.allclose(
        chain.apply(p, "voxel_centers", "MRI_surface_RAS_m"), expected, rtol=0, atol=1e-12
    )
    assert np.allclose(
        chain.apply(p, "voxel_centers", "scanner_RAS_m"),
        nib.affines.apply_affine(image.affine, p) * 0.001,
        atol=1e-12,
        rtol=0,
    )
    assert np.allclose(
        chain.apply(p, "voxel_centers", "head_m"),
        expected - [0.01, -0.02, 0.03],
        atol=1e-12,
        rtol=0,
    )


def test_lps_conversion_and_cross_frame_roundtrip():
    _, chain = image_chain()
    p = np.array([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]])
    ras = chain.apply(p, "voxel_centers", "scanner_RAS_m")
    lps = chain.apply(p, "voxel_centers", "scanner_LPS_m")
    assert np.allclose(lps, ras * [-1, -1, 1], rtol=0, atol=1e-12)
    head = chain.apply(lps, "scanner_LPS_m", "head_m")
    assert np.allclose(chain.apply(head, "head_m", "voxel_centers"), p, atol=1e-12, rtol=0)
    with pytest.raises(ValueError):
        chain.matrix("MRI", "head_m")


@pytest.mark.parametrize("fault", ["reflection", "singular", "mm", "nonfinite", "bad_direction"])
def test_invalid_affines_and_transform_direction(fault):
    image, chain = image_chain()
    a = chain.voxel_to_scanner_m.copy()
    t = chain.head_to_surface_m.copy()
    if fault == "reflection":
        t[0, 0] = -1
    elif fault == "singular":
        a[0] = 0
    elif fault == "mm":
        a[:3] *= 1000
    elif fault == "nonfinite":
        a[0, 0] = np.nan
    else:
        with pytest.raises(ValueError):
            MRIFrameChain.from_mgh(image, Transform(Frame.MRI, Frame.HEAD, np.eye(4)))
        return
    with pytest.raises(ValueError):
        MRIFrameChain(a, chain.voxel_to_surface_m, t)


def domain_fixture():
    a = np.diag([0.002, 0.003, 0.004, 1.0])
    a[0, 3] = 0.1
    mask = np.ones((4, 3, 2), bool)
    mask[0, 0, 0] = False
    return SourceDomain(mask, a)


def test_irregular_voxel_prior_measure_and_M31_consumption():
    domain = domain_fixture()
    p = domain.centers()[[0, -1]]
    weights = domain.weights(p)
    assert np.isclose(domain.volume_m3, 23 * 0.002 * 0.003 * 0.004, rtol=1e-12, atol=0)
    assert np.isclose(weights.sum(), domain.volume_m3, rtol=1e-12, atol=0)
    # These MRI coordinates lie outside the M31 ball; an explicit domain is required.
    with pytest.raises(ValueError):
        SourcePrior.create(p, "cell_volume")
    prior = SourcePrior.create(p, "cell_volume", domain=domain)
    assert np.isclose(prior.trace_Am2, 36e-16, rtol=1e-12, atol=0)
    assert np.allclose(prior.diagonal[::3], 12 * weights / domain.volume_m3, rtol=1e-12, atol=0)
    proj = average_projector(4)
    g = proj @ np.random.default_rng(32).normal(size=(4, 6)) * 100
    noise = NoiseModel((5e-8) ** 2 * proj, tuple("abcd"), proj)
    inv = PriorInverse(g, p, prior, noise, "MNE")
    assert np.isfinite(inv.kernel(1 / 9)).all() and inv.diagnostics(1 / 9)["EDF"] < 3


@pytest.mark.parametrize(
    "fault", ["outside", "duplicate", "nan", "wrong_frame", "nonbinary", "empty", "mass"]
)
def test_bad_anatomical_source_domain(fault):
    d = domain_fixture()
    p = d.centers()[[0, -1]]
    with pytest.raises(ValueError):
        if fault == "outside":
            d.positions(np.array([[0.5, 0, 0]]))
        elif fault == "duplicate":
            d.positions(np.repeat(p[:1], 2, axis=0))
        elif fault == "nan":
            d.positions(p * np.nan)
        elif fault == "wrong_frame":
            SourceDomain(d.mask, d.voxel_to_mri_m, frame="scanner_RAS_m")
        elif fault == "nonbinary":
            SourceDomain(d.mask.astype(int), d.voxel_to_mri_m)
        elif fault == "empty":
            SourceDomain(d.mask & False, d.voxel_to_mri_m)
        else:
            SourcePrior.create(p, "cell_volume", d.weights(p) * 2, domain=d)


def test_domain_shape_identity_and_mutability():
    d = domain_fixture()
    p = d.centers()[[0, -1]]
    v = SourcePrior.create(p, "cell_volume", domain=d)
    other = SourceDomain(d.mask[::-1].copy(), d.voxel_to_mri_m)
    assert d.identity != other.identity
    with pytest.raises(ValueError):
        d.mask[0, 0, 0] = True
    proj = average_projector(4)
    g = proj @ np.random.default_rng(33).normal(size=(4, 6))
    n = NoiseModel(proj, tuple("abcd"), proj)
    with pytest.raises(ValueError):
        PriorInverse(g, p[::-1], v, n, "MNE")


def test_QC_is_not_independent_anatomical_validation():
    checks = dict.fromkeys(COMPUTATIONAL_CHECKS, True)
    r = classify_anatomy(checks, MRI_derived=True, local_permission=True)
    assert r["status"] == "QC_ONLY_ANATOMY" and not r["anatomical_accuracy_established"]
    require_forward_ready(r)
    ref = {
        k: dict(
            independent=True,
            reference_role="conductor_boundary",
            provenance="synthetic independent test fixture",
            Dice=0.9,
            HD95_mm=1.0,
        )
        for k in ["inner_skull", "outer_skull", "scalp"]
    }
    valid = classify_anatomy(
        checks,
        MRI_derived=True,
        local_permission=True,
        conductor_references=ref,
        independent_tissue_validation=True,
    )
    assert valid["status"] == "VALIDATED_ANATOMY"
    ref["inner_skull"]["reference_role"] = "brain_tissue"
    assert (
        classify_anatomy(
            checks,
            MRI_derived=True,
            local_permission=True,
            conductor_references=ref,
            independent_tissue_validation=True,
        )["status"]
        == "NOT_READY_FOR_FORWARD_MODEL"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "topology",
        "nesting",
        "self_intersections",
        "coordinates",
        "electrodes",
        "sources",
        "materials",
        "permission",
        "MRI",
    ],
)
def test_failed_readiness_blocks_forward(fault):
    checks = dict.fromkeys(COMPUTATIONAL_CHECKS, True)
    if fault in checks:
        checks[fault] = False
    r = classify_anatomy(checks, MRI_derived=fault != "MRI", local_permission=fault != "permission")
    assert r["status"] == "NOT_READY_FOR_FORWARD_MODEL"
    with pytest.raises(ValueError):
        require_forward_ready(r)


def test_incomplete_evidence_and_failed_reference_not_hidden():
    with pytest.raises(ValueError):
        classify_anatomy({"topology": True}, MRI_derived=True, local_permission=True)
    r = classify_anatomy(
        dict.fromkeys(COMPUTATIONAL_CHECKS, True),
        MRI_derived=True,
        local_permission=True,
        conductor_references={},
    )
    assert r["status"] == "NOT_READY_FOR_FORWARD_MODEL"


def test_M31_and_M32_seals_preserved():
    for milestone in [31, 32]:
        root = Path(f"experiments/milestone{milestone}")
        seal = json.loads((root / "seal.json").read_text())
        assert (
            hashlib.sha256((root / "design.json").read_bytes()).hexdigest() == seal["design_sha256"]
        )
    m = json.loads(Path("experiments/milestone31/manifest.json").read_text())
    assert all(
        hashlib.sha256((Path("experiments/milestone31") / p).read_bytes()).hexdigest() == h
        for p, h in m.items()
    )


def test_mri_platform_comparator_rejects_changed_or_incomplete_reports(tmp_path):
    import json

    from scripts.compare_mri_head_models import compare
    from scripts.mri_head_repro import run

    report = run()
    paths = []
    for os, arch in [("Linux", "x86_64"), ("Darwin", "arm64")]:
        for py in ["3.11", "3.12"]:
            folder = tmp_path / (os + py)
            folder.mkdir()
            report["environment"] = dict(system=os, machine=arch, python=py + ".0")
            path = folder / "mri-head-model-synthetic.json"
            path.write_text(json.dumps(report))
            paths.append(path)
    assert compare(tmp_path)["all_passed"]
    changed = json.loads(paths[-1].read_text())
    changed["kernel"][0][0] += 0.001
    paths[-1].write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="elementwise"):
        compare(tmp_path)
    paths[-1].unlink()
    with pytest.raises(ValueError, match="Four"):
        compare(tmp_path)
