"""Independent geometry, typed execution, cache recovery and adversarial contracts."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from soma.core.provenance import sha256
from soma.geometry import Frame, Transform
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.registration import from_sitk, to_sitk
from soma.imaging.resampling import resample
from soma.imaging.volumes import Volume
from soma.pipeline.backends import Precomputed
from soma.pipeline.cache import StageCache
from soma.pipeline.contracts import (
    InputRecord,
    StageSpec,
    ordered_graph,
    read_transform,
    transform_receipt,
)
from soma.pipeline.derivatives import private_output, validate_derivatives
from soma.pipeline.engine import configuration, run_pipeline
from soma.pipeline.stages import execute_stage, intensity_qc, preprocess


def fixture_image(tmp_path):
    xyz = np.indices((17, 17, 17)).transpose(1, 2, 3, 0) - 8
    r = np.linalg.norm(xyz, axis=-1)
    x = np.zeros(r.shape, dtype=np.float32)
    x[r < 7] = 20
    x[r < 5] = 70
    x[r < 3] = 120
    p = tmp_path / "source" / "input.nii.gz"
    p.parent.mkdir(parents=True)
    save_nifti(Volume(x, np.diag([0.001, 0.0015, 0.002, 1])), p)
    return p


def cfg():
    c = configuration(Path("configs/mri-pipeline.yaml"))
    c["visualization"] = False
    return c


def test_graph_topological_order_and_contracts():
    a = StageSpec("a", (), {"input": "dict"}, {"x": "dict"})
    b = StageSpec("b", ("a",), {"x": "dict"}, {"y": "dict"})
    assert [s.name for s in ordered_graph([b, a], {"input"})] == ["a", "b"]


@pytest.mark.parametrize("kind", ["cycle", "missing", "duplicate", "unavailable"])
def test_invalid_graphs(kind):
    if kind == "cycle":
        stages = [StageSpec("a", ("b",), {}, {}), StageSpec("b", ("a",), {}, {})]
    elif kind == "missing":
        stages = [StageSpec("a", ("absent",), {}, {})]
    elif kind == "duplicate":
        stages = [StageSpec("a", (), {}, {"x": "dict"}), StageSpec("b", (), {}, {"x": "dict"})]
    else:
        stages = [StageSpec("a", (), {"missing": "dict"}, {})]
    with pytest.raises(ValueError):
        ordered_graph(stages, set())


def test_complete_pipeline_resume_and_cross_run_stage_hits(tmp_path):
    p = fixture_image(tmp_path)
    record = InputRecord(p, "01")
    c = cfg()
    cache = tmp_path / "cache"
    first = run_pipeline(
        record, c, tmp_path / "out", report_root=tmp_path / "reports", cache_root=cache
    )
    assert first["status"] == "complete" and first["cache_misses"] == 11
    resumed = run_pipeline(
        record, c, tmp_path / "out", report_root=tmp_path / "reports", cache_root=cache, resume=True
    )
    assert (
        resumed["resume_verified"]
        and resumed["verified_output_reuse"]
        and resumed["stage_cache_reads"] == 0
    )
    second = run_pipeline(
        record, c, tmp_path / "out2", report_root=tmp_path / "reports2", cache_root=cache
    )
    assert second["cache_hits"] == 11
    original = load_nifti(p)
    export = load_nifti(next((tmp_path / "out").rglob("*preproc_T1w.nii.gz")))
    assert_allclose(export.array(), original.array())
    assert export.same_grid(original)


def test_interrupted_run_recovers_committed_stages(tmp_path):
    record = InputRecord(fixture_image(tmp_path), "01")
    c = cfg()
    cache = tmp_path / "cache"
    with pytest.raises(InterruptedError):
        run_pipeline(
            record,
            c,
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=cache,
            interrupt_after="preprocessing",
        )
    journal = json.loads((tmp_path / "reports/sub-01/run.json").read_text())
    assert journal["status"] == "interrupted"
    result = run_pipeline(
        record, c, tmp_path / "out", report_root=tmp_path / "reports", cache_root=cache, resume=True
    )
    assert result["status"] == "complete" and result["cache_hits"] == 4


def test_modified_derivative_resume_refused(tmp_path):
    record = InputRecord(fixture_image(tmp_path), "01")
    c = cfg()
    run_pipeline(
        record, c, tmp_path / "out", report_root=tmp_path / "reports", cache_root=tmp_path / "cache"
    )
    next((tmp_path / "out").rglob("*dseg.nii.gz")).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="changed"):
        run_pipeline(
            record,
            c,
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
            resume=True,
        )


def test_duplicate_export_and_stale_resume_fail(tmp_path):
    record = InputRecord(fixture_image(tmp_path), "01")
    c = cfg()
    run_pipeline(
        record, c, tmp_path / "out", report_root=tmp_path / "reports", cache_root=tmp_path / "cache"
    )
    with pytest.raises(FileExistsError):
        run_pipeline(
            record,
            c,
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
        )
    changed = deepcopy(c)
    changed["n4"]["iterations"] = [1]
    with pytest.raises(ValueError, match="identity"):
        run_pipeline(
            record,
            changed,
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
            resume=True,
        )
    with pytest.raises(FileExistsError):
        run_pipeline(
            record,
            c,
            tmp_path / "out",
            report_root=tmp_path / "reports2",
            cache_root=tmp_path / "cache",
        )


def test_content_cache_key_and_explicit_corruption_repair(tmp_path):
    cache = StageCache(tmp_path)

    def build():
        return {"x": np.array([1.0, 2.0])}

    a, first = cache.run("test", {"in": 1}, {"p": 1}, build)
    b, hit = cache.run("test", {"in": 1}, {"p": 1}, build)
    assert hit["hit"] and not first["hit"]
    assert_allclose(a["x"], b["x"])
    _, different = cache.run("test", {"in": 1}, {"p": 2}, build)
    assert different["cache_key"] != first["cache_key"]
    Path(first["path"]).write_bytes(b"bad cache")
    with pytest.raises(ValueError, match="integrity"):
        cache.run("test", {"in": 1}, {"p": 1}, build)
    _, repair = StageCache(tmp_path, repair=True).run("test", {"in": 1}, {"p": 1}, build)
    assert repair["recovery"]["reason"] == "corrupt committed cache" and not repair["hit"]


def test_half_published_cache_recovery_is_explicit(tmp_path):
    cache = StageCache(tmp_path)

    def build():
        return {"a": 3}

    _, receipt = cache.run("stage", {}, {}, build)
    Path(receipt["path"] + ".json").unlink()
    with pytest.raises(ValueError):
        cache.run("stage", {}, {}, build)
    _, recovered = StageCache(tmp_path, recover=True).run("stage", {}, {}, build)
    assert recovered["recovery"]["reason"] == "incomplete publication"


def test_dry_run_never_writes(tmp_path):
    record = InputRecord(fixture_image(tmp_path), "01")
    result = run_pipeline(
        record,
        cfg(),
        tmp_path / "output",
        report_root=tmp_path / "reports",
        cache_root=tmp_path / "cache",
        dry_run=True,
    )
    assert result["status"] == "dry-run" and len(result["stages"]) == 11
    assert not (tmp_path / "output").exists() and not (tmp_path / "cache").exists()


@pytest.mark.parametrize("subject", ["../01", "01_bad", "01/session", ""])
def test_invalid_entities_rejected(tmp_path, subject):
    with pytest.raises(ValueError):
        InputRecord(tmp_path / "input.nii", subject)


def test_legacy_permission_boundary(tmp_path):
    with pytest.raises(ValueError):
        InputRecord(
            tmp_path / "LabelsForTesting.nii",
            "01",
            dataset_type="legacy",
            legacy={"dataset": "mrbrains13", "partition": "test"},
        )


@pytest.mark.parametrize(
    "values", [np.ones((3, 3, 3)), np.full((3, 3, 3), np.nan), np.ones((3, 3, 3)) * -1]
)
def test_nonfinite_constant_or_nonpositive_input(values):
    with pytest.raises(ValueError):
        intensity_qc(Volume(values, np.diag([0.001, 0.001, 0.001, 1])))


def test_import_backend_identity_missing_file_and_mapping(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    backend = Precomputed()
    params = {
        "subject": "wrong",
        "path": str(tmp_path / "missing.nii"),
        "tool": "External",
        "version": "1",
        "model": "none",
        "mapping": {0: 0},
        "input_sha256": image.metadata["source_sha256"],
        "reference_used": False,
    }
    with pytest.raises(ValueError, match="matched subject"):
        backend.segment(image, subject="01", parameters=params)
    params["subject"] = "01"
    with pytest.raises(FileNotFoundError):
        backend.segment(image, subject="01", parameters=params)
    p = tmp_path / "labels.nii.gz"
    save_nifti(Volume(np.ones(image.shape, dtype=np.uint8) * 7, image.affine_m, "labels"), p)
    params["path"] = str(p)
    with pytest.raises(ValueError, match="ontology"):
        backend.segment(image, subject="01", parameters=params)


@pytest.mark.parametrize("kind", ["empty", "grid", "subject"])
def test_mask_adversaries(tmp_path, kind):
    image = load_nifti(fixture_image(tmp_path))
    values = np.zeros(image.shape, dtype=np.uint8)
    if kind != "empty":
        values[2:5, 2:5, 2:5] = 1
    a = image.affine_m.copy()
    if kind == "grid":
        a[0, 3] += 0.01
    p = tmp_path / "mask.nii.gz"
    save_nifti(Volume(values, a, "labels"), p)
    with pytest.raises(ValueError):
        execute_stage(
            "mask",
            {"processed": image, "record": {"subject": "01"}},
            {"policy": "import", "path": str(p), "subject": "other" if kind == "subject" else "01"},
            None,
        )


def test_label_validation_rejects_unknown_labels(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    labels = Volume(np.ones(image.shape, dtype=np.uint8) * 9, image.affine_m, "labels")
    with pytest.raises(ValueError, match="ontology"):
        execute_stage("label_validation", {"labels": labels, "processed": image}, {}, None)


def test_transform_roundtrip_composition_independent_oracle():
    a = np.eye(4)
    a[:3, 3] = [0.01, 0.02, -0.03]
    t = Transform(Frame.RAS, Frame.RAS, a)
    value = transform_receipt(
        t, {}, {}, interpolation="linear", provenance="oracle known translation"
    )
    recovered = read_transform(value)
    assert_allclose(recovered.then(recovered.inverse()).matrix, np.eye(4), atol=1e-15)
    assert_allclose(recovered.matrix @ np.array([0.1, 0.2, 0.3, 1]), [0.11, 0.22, 0.27, 1])


@pytest.mark.parametrize(
    "field,value", [("units", "mm"), ("direction", "source_to_reference"), ("type", "nonlinear")]
)
def test_wrong_transform_semantics_rejected(field, value):
    r = transform_receipt(
        Transform(Frame.RAS, Frame.RAS, np.eye(4)),
        {},
        {},
        interpolation="linear",
        provenance="test",
    )
    r[field] = value
    with pytest.raises(ValueError):
        read_transform(r)


def test_cross_library_nibabel_sitk_world_geometry(tmp_path):
    a = np.array([[0, -0.002, 0, 0.01], [0.001, 0, 0, -0.02], [0, 0, 0.003, 0.03], [0, 0, 0, 1.0]])
    values = np.arange(60, dtype=np.float32).reshape(3, 4, 5)
    v = Volume(values, a)
    s = to_sitk(v)
    # Independent LPS millimetre world coordinate at voxel(1,2,3).
    assert_allclose(s.TransformIndexToPhysicalPoint((1, 2, 3)), [-6.0, 19.0, 39.0], atol=1e-12)
    back = from_sitk(s)
    assert_allclose(back.affine_m, a, atol=1e-15)
    assert_allclose(back.array(), values)
    p = tmp_path / "roundtrip.nii.gz"
    save_nifti(back, p)
    loaded = load_nifti(p)
    assert_allclose(loaded.affine_m, a, atol=2e-9)
    assert_allclose(abs(np.linalg.det(loaded.affine_m[:3, :3])) * 1e9, 6.0, rtol=1e-7)


def test_label_nearest_neighbor_identity_and_half_voxel_shift():
    data = np.zeros((4, 4, 4), dtype=np.uint8)
    data[1:3] = 2
    a = np.diag([0.001, 0.002, 0.003, 1])
    v = Volume(data, a, "labels")
    assert_allclose(resample(v, v, order=0).array(), data)
    with pytest.raises(ValueError):
        resample(v, v, order=1)
    b = a.copy()
    b[0, 3] = 0.001
    ref = Volume(np.zeros_like(data), b, "labels")
    expected = np.zeros_like(data)
    expected[:2] = 2
    assert_allclose(resample(v, ref, order=0).array(), expected)


def test_synthetic_n4_preserves_grid_and_reports_iterations(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    out, q = preprocess(
        image,
        {
            "n4": {"enabled": True, "iterations": [2], "shrink_factor": 1},
            "resampling": {"enabled": False},
        },
    )
    assert image.same_grid(out) and np.isfinite(out.array()).all()
    assert q["n4"]["elapsed_iterations"] >= 1 and q["n4"]["mask_source"].startswith("positive")


def test_private_outputs_and_invalid_derivative_metadata(tmp_path):
    with pytest.raises(ValueError):
        private_output(Path("docs/private-patient"))
    p = tmp_path / "dataset_description.json"
    p.write_text(json.dumps({"DatasetType": "raw"}))
    with pytest.raises(ValueError, match="description"):
        validate_derivatives(tmp_path, full=False)


def test_crash_after_atomic_export_recovers_without_overwrite(tmp_path, monkeypatch):
    import soma.pipeline.engine as engine

    record = InputRecord(fixture_image(tmp_path), "01")
    c = cfg()
    original = engine.export_subject

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated crash after export publication")

    monkeypatch.setattr(engine, "export_subject", interrupted)
    with pytest.raises(RuntimeError):
        run_pipeline(
            record,
            c,
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
        )
    product = next((tmp_path / "out").rglob("*dseg.nii.gz"))
    before = sha256(product)
    monkeypatch.setattr(engine, "export_subject", original)
    recovered = run_pipeline(
        record,
        c,
        tmp_path / "out",
        report_root=tmp_path / "reports",
        cache_root=tmp_path / "cache",
        resume=True,
    )
    assert (
        recovered["status"] == "complete"
        and recovered["cache_hits"] == 11
        and sha256(product) == before
    )


def test_cache_geometry_identity(tmp_path):
    cache = StageCache(tmp_path)
    a = Volume(np.ones((2, 2, 2)), np.diag([0.001, 0.001, 0.001, 1]))
    b = Volume(np.ones((2, 2, 2)), np.diag([0.002, 0.001, 0.001, 1]))
    _, first = cache.run("geometry", {"image": a}, {}, lambda: {"x": 1})
    _, second = cache.run("geometry", {"image": b}, {}, lambda: {"x": 1})
    assert first["cache_key"] != second["cache_key"] and not second["hit"]


@pytest.mark.parametrize("mode", ["unknown-unit", "qform-conflict", "corrupt"])
def test_bad_input_headers_stop_ingestion_with_journal(tmp_path, mode):
    import nibabel as nib

    p = fixture_image(tmp_path)
    if mode == "corrupt":
        p.write_bytes(b"not a NIfTI volume")
    else:
        image = nib.load(p)
        if mode == "unknown-unit":
            image.header.set_xyzt_units("unknown")
        else:
            q = image.affine.copy()
            q[0, 3] += 10
            image.set_qform(q, code=2)
        nib.save(image, p)
    with pytest.raises((ValueError, nib.filebasedimages.ImageFileError, OSError)):
        run_pipeline(
            InputRecord(p, "01"),
            cfg(),
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
        )
    r = json.loads((tmp_path / "reports/sub-01/run.json").read_text())
    assert (
        r["status"] == "failed"
        and r["failed_stage"] == "ingestion"
        and not (tmp_path / "out").exists()
    )


def test_source_dataset_writes_refused(tmp_path):
    p = fixture_image(tmp_path)
    with pytest.raises(ValueError, match="source dataset"):
        run_pipeline(
            InputRecord(p, "01"),
            cfg(),
            p.parent / "output",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
        )


def test_standalone_volume_never_claimed_original_bids(tmp_path):
    p = fixture_image(tmp_path)
    assert InputRecord(p, "01").dataset_type == "standalone"
    with pytest.raises(ValueError, match="BIDS origin"):
        InputRecord(p, "01", dataset_type="bids")


def test_import_backend_success_with_explicit_nonstandard_mapping(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    data = np.zeros(image.shape, dtype=np.uint16)
    data[2:5] = 10
    data[5:8] = 20
    data[8:11] = 30
    p = tmp_path / "precomputed.nii.gz"
    save_nifti(Volume(data, image.affine_m, "labels"), p)
    labels, receipt = Precomputed().segment(
        image,
        subject="01",
        parameters={
            "path": str(p),
            "subject": "01",
            "tool": "Synthetic external fixture",
            "version": "1",
            "model": "fixture",
            "mapping": {0: 0, 10: 1, 20: 2, 30: 3},
            "input_sha256": image.metadata["source_sha256"],
            "reference_used": False,
        },
    )
    assert_allclose(labels.array(), data // 10)
    assert receipt["backend"] == "Synthetic external fixture" and receipt["reference_used"] is False


def test_external_backend_cache_identity_is_required_and_distinct():
    from soma.pipeline.backends import BACKENDS, backend_identity, register_backend

    class External:
        cache_version = "model-v1"

        def segment(self, image, *, subject, parameters):
            raise NotImplementedError

    name = "unit-external-fixture"
    try:
        register_backend(name, External())
        first = backend_identity(name)
        BACKENDS[name].cache_version = "model-v2"
        assert backend_identity(name) != first
        with pytest.raises(ValueError):
            register_backend(name, External())
    finally:
        BACKENDS.pop(name, None)


def test_all_volume_mask_is_rejected(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    p = tmp_path / "all-mask.nii.gz"
    save_nifti(Volume(np.ones(image.shape, dtype=np.uint8), image.affine_m, "labels"), p)
    with pytest.raises(ValueError, match="all-volume"):
        execute_stage(
            "mask",
            {"processed": image, "record": {"subject": "01"}},
            {
                "policy": "import",
                "path": str(p),
                "subject": "01",
                "input_sha256": image.metadata["source_sha256"],
            },
            None,
        )


def test_optional_reference_grid_resampling_tracks_direction(tmp_path):
    image = load_nifti(fixture_image(tmp_path))
    p = tmp_path / "target.nii.gz"
    a = image.affine_m.copy()
    a[0, 3] += 0.001
    save_nifti(Volume(np.zeros(image.shape, dtype=np.float32), a), p)
    out, q = preprocess(
        image, {"n4": {"enabled": False}, "resampling": {"enabled": True, "reference": str(p)}}
    )
    assert out.same_grid(load_nifti(p)) and len(q["transforms"]) == 1
    t = q["transforms"][0]
    assert t["direction"] == "reference_world_to_source_world"
    assert_allclose(t["matrix"], np.eye(4))
    assert t["interpolation"] == "linear" and "no registration" in t["provenance"]


def test_resume_cannot_mutate_published_label_ontology(tmp_path, monkeypatch):
    import soma.pipeline.engine as engine

    record = InputRecord(fixture_image(tmp_path), "01")
    original = engine.export_subject

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after publication")

    monkeypatch.setattr(engine, "export_subject", interrupted)
    with pytest.raises(RuntimeError):
        run_pipeline(
            record,
            cfg(),
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
        )
    lut = next((tmp_path / "out").rglob("*dseg.tsv"))
    lut.write_text(lut.read_text().replace("Cerebrospinal Fluid", "Skull"))
    monkeypatch.setattr(engine, "export_subject", original)
    with pytest.raises(ValueError, match="mapping"):
        run_pipeline(
            record,
            cfg(),
            tmp_path / "out",
            report_root=tmp_path / "reports",
            cache_root=tmp_path / "cache",
            resume=True,
        )


def test_ibsr_bridge_does_not_require_mrbrains_installation(tmp_path):
    from soma.pipeline.ingestion import legacy_records

    root = tmp_path / "ibsr"
    d = root / "IBSR_99"
    d.mkdir(parents=True)
    (root / "README.txt").write_text("Synthetic fixture notice: Rohlfing citation requested.")
    values = np.zeros((4, 4, 4), dtype=np.int16)
    for suffix, kind in [("ana_strip", "intensity"), ("segTRI_ana", "labels")]:
        save_nifti(
            Volume(values, np.diag([0.001, 0.0015, 0.001, 1]), kind), d / f"IBSR_99_{suffix}.nii.gz"
        )
    records = legacy_records(root, tmp_path / "not-installed", dataset="ibsr")
    assert len(records) == 1 and records[0].dataset_type == "legacy"
    assert records[0].metadata["origin"].startswith("legacy non-BIDS")
