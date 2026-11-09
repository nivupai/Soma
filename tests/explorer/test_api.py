"""Offline HTTP, geometry, numerical-adapter and privacy regression tests."""

import json
import threading

import nibabel as nib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.jobs import Jobs
from services.explorer_api.models import JobRequest
from services.explorer_api.registry import Configuration, Registry
from services.explorer_api.science import Science
from soma.core.signal import Signal
from soma.signal.spectral import WelchConfig, welch


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(jobs_root=tmp_path / "jobs"), base_url="http://127.0.0.1") as c:
        yield c


@pytest.mark.parametrize(
    "path",
    [
        "/catalog",
        "/eeg/demo-eeg/metadata",
        "/eeg/demo-eeg/window",
        "/eeg/demo-eeg/analysis",
        "/volumes/demo-mri",
        "/volumes/demo-mri/slice",
        "/sources/demo-source/mesh",
        "/sources/demo-source/series",
        "/fmri/demo-fmri",
        "/experiments",
        "/qc",
        "/experiments/demo-calibration/export?format=csv",
    ],
)
def test_demo_endpoints_work_without_files_or_downloads(client, path):
    response = client.get("/api" + path)
    assert response.status_code == 200
    assert "/Users/" not in response.text
    if path == "/experiments":
        assert response.json()[0]["state"] == "EXPLORATORY"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_native_analysis_independent_of_display_reduction(client):
    meta = client.get("/api/eeg/demo-eeg/metadata").json()["data"]
    assert meta["units"] == "V" and meta["fs_hz"] == 160
    assert "imagery" in meta["events"][0]["label"]
    native = client.get("/api/eeg/demo-eeg/window?points=2048&duration_s=10").json()["data"]
    reduced = client.get("/api/eeg/demo-eeg/window?points=32&duration_s=10").json()["data"]
    a = client.get("/api/eeg/demo-eeg/analysis").json()["data"]
    assert len(reduced["times_s"]) <= 32 < len(native["times_s"])
    assert a["n_analysis_samples"] == 1600
    reference = welch(Signal(np.array(native["values_V"][0]), 160), WelchConfig(160, 80))
    np.testing.assert_allclose(a["density_V2_Hz"], reference.density, rtol=1e-12)
    assert np.all(np.array(reduced["lower_V"]) <= np.array(reduced["upper_V"]))
    fractional = client.get("/api/eeg/demo-eeg/analysis?start_s=0.333").json()["data"]
    assert fractional["tf_times_s"][0] == round(0.333 * meta["fs_hz"]) / meta["fs_hz"]


@pytest.mark.parametrize(
    "suffix", ["?start_s=-1", "?duration_s=31", "?channels=bad", "?points=9999", "?start_s=59"]
)
def test_bounded_eeg_queries(client, suffix):
    assert client.get("/api/eeg/demo-eeg/window" + suffix).status_code == 422


def test_policy_cannot_be_bypassed(client):
    assert client.get("/api/fmri/demo-fmri?inference=confirmatory").status_code == 422
    result = client.get("/api/fmri/demo-fmri").json()
    assert result["provenance"]["confirmatory_claim_allowed"] is False
    assert result["data"]["metadata"]["confirmatory_claim_allowed"] is False
    assert client.get("/api/qc").json()["human_retest"] == "NOT_AVAILABLE"


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Origin": "https://evil.example"}, 403),
        ({"Origin": "null"}, 403),
        ({"Host": "evil.example"}, 400),
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Origin": "http://127.0.0.1:5173"}, 200),
    ],
)
def test_origin_and_host_boundaries(client, headers, status):
    assert client.get("/api/catalog", headers=headers).status_code == status


def test_oversized_and_arbitrary_code_requests(client):
    assert client.post("/api/jobs", content=b"x" * 17000).status_code == 413
    assert client.post("/api/jobs", json={"kind": "shell", "code": "print(1)"}).status_code == 422
    assert client.get("/api/files?path=/etc/passwd").status_code == 404
    assert client.get("/api/volumes/%2e%2e%2fsecret").status_code == 404


def registry_for_volume(tmp_path, *, segmentation=True, unknown=False):
    data = np.arange(5 * 6 * 7, dtype=np.float32).reshape(5, 6, 7)
    affine = np.array(
        [[-2.0, 0.0, 0.0, 14.0], [0.0, 0.0, 4.0, -6.0], [0.0, 3.0, 0.0, 2.0], [0.0, 0.0, 0.0, 1.0]]
    )
    image = nib.Nifti1Image(data, affine)
    if not unknown:
        image.header.set_xyzt_units("mm")
    nib.save(image, tmp_path / "image.nii.gz")
    seg = nib.Nifti1Image((data > 100).astype(np.uint8), affine)
    seg.header.set_xyzt_units("mm")
    nib.save(seg, tmp_path / "labels.nii.gz")
    entry = {
        "id": "local-volume",
        "kind": "mri",
        "label": "Synthetic permuted grid",
        "root": "allowed",
        "file": "image.nii.gz",
        "frame": "synthetic-RAS",
        "synthetic": True,
    }
    if segmentation:
        entry["segmentation"] = "labels.nii.gz"
    return Registry(
        Configuration.model_validate({"roots": {"allowed": str(tmp_path)}, "entries": [entry]})
    ), image


@pytest.mark.parametrize("plane", ["axial", "coronal", "sagittal"])
def test_permuted_anisotropic_affine_and_aligned_labels(tmp_path, plane):
    registry, image = registry_for_volume(tmp_path)
    science = Science(registry)
    canonical = nib.as_closest_canonical(image)
    voxel = [2, 3, 4]
    s = science.slice("local-volume", plane, voxel)
    np.testing.assert_allclose(s.world_mm, (canonical.affine @ [*voxel, 1])[:3])
    assert science.volume_meta("local-volume").orientation == ["R", "A", "S"]
    matrix = np.array(s.pixel_to_world_mm)
    world = matrix @ [0, 0, 0, 1]
    ijk = np.linalg.solve(canonical.affine, world)[:3].round().astype(int)
    assert s.values[0][0] == canonical.get_fdata()[tuple(ijk)]
    assert s.labels[0][0] == int(s.values[0][0] > 100)
    assert s.horizontal_labels == (["P", "A"] if plane == "sagittal" else ["L", "R"])
    science.close()


def test_unknown_units_rejected_without_explicit_override(tmp_path):
    registry, _ = registry_for_volume(tmp_path, unknown=True)
    science = Science(registry)
    with pytest.raises(ValueError, match="units"):
        science.volume_meta("local-volume")
    science.close()


def test_misaligned_segmentation_rejected(tmp_path):
    registry, _ = registry_for_volume(tmp_path)
    image = nib.load(tmp_path / "labels.nii.gz")
    affine = image.affine.copy()
    affine[0, 3] += 3
    wrong = nib.Nifti1Image(image.get_fdata().astype(np.uint8), affine)
    wrong.header.set_xyzt_units("mm")
    nib.save(wrong, tmp_path / "labels.nii.gz")
    science = Science(registry)
    with pytest.raises(ValueError, match="aligned"):
        science.volume_meta("local-volume")
    science.close()


@pytest.mark.parametrize("file", ["../private.json", "/etc/passwd"])
def test_configured_traversal_rejected(tmp_path, file):
    with pytest.raises(ValueError):
        Registry(
            Configuration.model_validate(
                {
                    "roots": {"root": str(tmp_path)},
                    "entries": [
                        {
                            "id": "bad",
                            "kind": "experiment",
                            "label": "Bad",
                            "root": "root",
                            "file": file,
                        }
                    ],
                }
            )
        )


def test_symlink_revalidated_after_cache(tmp_path):
    registry, _ = registry_for_volume(tmp_path, segmentation=False)
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as c:
        assert c.get("/api/volumes/local-volume").status_code == 200
        path = tmp_path / "image.nii.gz"
        path.unlink()
        path.symlink_to("/etc/passwd")
        assert c.get("/api/volumes/local-volume").status_code == 422
        assert c.get("/api/catalog").json()["datasets"][-1]["available"] is False


def test_job_capacity_and_cooperative_cancellation(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def work(request):
        entered.set()
        release.wait(3)
        raise RuntimeError("cancelled test work")

    jobs = Jobs(work, tmp_path)
    try:
        request = JobRequest(dataset_id="demo-eeg", channel="C3", start_s=0, duration_s=10)
        a = jobs.submit(request)
        assert entered.wait(2)
        b = jobs.submit(request)
        with pytest.raises(ValueError, match="capacity"):
            jobs.submit(request)
        assert jobs.cancel(a.id).status == "cancelled"
        assert jobs.cancel(b.id).status == "cancelled"
        release.set()
    finally:
        release.set()
        jobs.close()
    assert not list(tmp_path.glob("*.json"))


def test_compatible_comparison_export_and_incompatibility(tmp_path):
    (tmp_path / "receipt.json").write_text(
        json.dumps(
            {
                "=formula": 3,
                "metric": 0.2,
                "path": "/Users/private",
                "_interpretation_state": "CONFIRMATORY",
                "source_error_mm": 1.2,
                "rows": list(range(201)),
                "source": {"method": "inverse", "resource": "data/external/private/image.nii.gz"},
            }
        )
    )
    compatibility = {
        "units": "probability",
        "estimand": "same",
        "frame": "nonspatial",
        "processing": "same",
    }
    entries = [
        {
            "id": i,
            "kind": "experiment",
            "label": i,
            "root": "root",
            "file": "receipt.json",
            "compatibility": compatibility if i != "different" else {**compatibility, "units": "V"},
        }
        for i in ["first", "second", "different"]
    ]
    registry = Registry(
        Configuration.model_validate({"roots": {"root": str(tmp_path)}, "entries": entries})
    )
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as c:
        assert (
            c.post("/api/experiments/compare", json={"ids": ["first", "second"]}).status_code == 200
        )
        assert (
            c.post("/api/experiments/compare", json={"ids": ["first", "different"]}).status_code
            == 409
        )
        exported = c.get("/api/experiments/first/export?format=csv")
        assert "'=formula" in exported.text
        import csv
        import io

        exported_rows = dict(list(csv.reader(io.StringIO(exported.text)))[1:])
        assert json.loads(exported_rows["_interpretation_state"]) == "DESCRIPTIVE_ONLY"
        assert "/Users/private" not in c.get("/api/experiments").text
        metrics = c.get("/api/experiments/first/export").json()["metrics"]
        assert metrics["rows"] == list(range(201))
        assert metrics["source_error_mm"] == 1.2
        assert metrics["source"]["method"] == "inverse"
        assert metrics["source"]["resource"] == "[private resource]"
        assert "path" not in metrics


def test_openapi_typed_contracts(client):
    schema = client.get("/openapi.json").json()
    assert "EEGWindow" in schema["components"]["schemas"]
    assert "pixel_to_world_mm" in schema["components"]["schemas"]["Slice"]["properties"]


def test_source_operators_and_geometry_are_sealed_and_frame_explicit(tmp_path):
    import hashlib

    np.savez(
        tmp_path / "estimate.npz",
        estimate=np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]]),
        times_s=np.array([0.0, 0.1, 0.2]),
    )
    np.savez(
        tmp_path / "geometry.npz",
        source_head_m=np.array([[0.01, 0.0, 0.0], [-0.01, 0.0, 0.0]]),
        sensor_head_m=np.array([[0.0, 0.1, 0.0]]),
    )
    np.savez(
        tmp_path / "operators.npz",
        assumed_forward=2 * np.eye(2),
        primary_inverse_kernel=0.1 * np.eye(2),
    )
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.glob("*.npz")}
    (tmp_path / "manifest.json").write_text(json.dumps({"result_files_sha256": hashes}))
    config = {
        "roots": {"root": str(tmp_path)},
        "entries": [
            {
                "id": "source",
                "kind": "source",
                "label": "Sealed synthetic source",
                "root": "root",
                "file": "estimate.npz",
                "geometry": "geometry.npz",
                "operators": "operators.npz",
                "manifest": "manifest.json",
                "frame": "MNE-head",
                "units": "A m",
                "synthetic": True,
            }
        ],
    }
    with TestClient(
        create_app(Registry(Configuration.model_validate(config))), base_url="http://127.0.0.1"
    ) as c:
        mesh = c.get("/api/sources/source/mesh")
        assert mesh.status_code == 200
        assert mesh.json()["data"]["frame"] == "MNE-head"
        assert mesh.json()["data"]["points_mm"][0] == [10.0, 0.0, 0.0]
        series = c.get("/api/sources/source/series?index=0").json()["data"]
        np.testing.assert_allclose(series["point_spread"], [0.2, 0.0])
        assert series["units"] == "A m"
        np.savez(
            tmp_path / "geometry.npz", source_head_m=np.array([[0.02, 0.0, 0.0], [-0.01, 0.0, 0.0]])
        )
        assert c.get("/api/sources/source/mesh").status_code == 422


def test_volume_cache_invalidates_on_registered_file_change(tmp_path):
    registry, _ = registry_for_volume(tmp_path, segmentation=False)
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as c:
        before = c.get("/api/volumes/local-volume/slice?x=2&y=2&z=2").json()["data"]["values"]
        image = nib.load(tmp_path / "image.nii.gz")
        replacement = nib.Nifti1Image(image.get_fdata().astype(np.float32) + 1000, image.affine)
        replacement.header.set_xyzt_units("mm")
        nib.save(replacement, tmp_path / "image.nii.gz")
        after = c.get("/api/volumes/local-volume/slice?x=2&y=2&z=2").json()["data"]["values"]
        np.testing.assert_allclose(np.array(after) - np.array(before), 1000)


def test_raw_bold_reports_metadata_without_producing_activation(tmp_path):
    image = nib.Nifti1Image(np.zeros((3, 4, 5, 10), np.float32), np.eye(4))
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_zooms((1, 1, 1, 2))
    nib.save(image, tmp_path / "bold.nii.gz")
    registry = Registry(
        Configuration.model_validate(
            {
                "roots": {"root": str(tmp_path)},
                "entries": [
                    {
                        "id": "raw-bold",
                        "kind": "fmri",
                        "label": "Raw BOLD",
                        "root": "root",
                        "file": "bold.nii.gz",
                        "role": "bold",
                    }
                ],
            }
        )
    )
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as c:
        response = c.get("/api/fmri/raw-bold").json()
        assert response["state"] == "NOT_AVAILABLE"
        data = response["data"]
        assert data["metadata"]["tr_s"] == 2
        assert data["metadata"]["confirmatory_claim_allowed"] is False
        assert data["design"] == []
        assert c.get("/api/volumes/raw-bold").status_code == 422


def test_sealed_experiment_and_figure_tampering_rejected(tmp_path):
    import hashlib

    summary = tmp_path / "summary.json"
    figure = tmp_path / "figure.png"
    summary.write_text('{"metric": 0.2}')
    figure.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    original = summary.read_bytes()
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [summary, figure]}
    (tmp_path / "manifest.json").write_text(json.dumps({"outputs_sha256": hashes}))
    registry = Registry(
        Configuration.model_validate(
            {
                "roots": {"root": str(tmp_path)},
                "entries": [
                    {
                        "id": "receipt",
                        "kind": "experiment",
                        "label": "Sealed receipt",
                        "root": "root",
                        "file": "summary.json",
                        "manifest": "manifest.json",
                        "figures": ["figure.png"],
                    }
                ],
            }
        )
    )
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as c:
        assert c.get("/api/experiments/receipt/export").status_code == 200
        assert c.get("/api/experiments/receipt/figures/0").status_code == 200
        summary.write_text('{"metric": 0.9}')
        assert c.get("/api/experiments/receipt/export").status_code == 422
        summary.write_bytes(original)
        figure.write_bytes(b"\x89PNG\r\n\x1a\nchanged")
        assert c.get("/api/experiments/receipt/figures/0").status_code == 422


def test_completed_job_persists_hashed_result_and_code_provenance(tmp_path):
    import hashlib

    root = tmp_path / "jobs"
    app = create_app(jobs_root=root)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        response = c.post(
            "/api/jobs",
            json={"dataset_id": "demo-eeg", "channel": "C3", "start_s": 0, "duration_s": 10},
        )
        assert response.status_code == 202
        identity = response.json()["id"]
        app.state.jobs.close()
        job = c.get(f"/api/jobs/{identity}").json()
        assert job["status"] == "completed" and job["progress"] == 1
        manifest = json.loads((root / (identity + ".json")).read_text())
        result = (root / (identity + ".result.json")).read_bytes()
        assert manifest["result_sha256"] == hashlib.sha256(result).hexdigest()
        from importlib.metadata import version

        assert manifest["provenance"]["application_version"] == version("soma-neuro")
        assert len(manifest["provenance"]["soma_source_sha256"]) == 64
        assert json.loads(result)["provenance"]["confirmatory_claim_allowed"] is False
