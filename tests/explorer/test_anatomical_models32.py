"""No human data: adversarial access controls and aggregate evidence boundaries."""

import copy
import json

import nibabel as nib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.explorer_api.anatomical_models import example
from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Registry
from soma.anatomy.public_head_models import read_public_head_models, validate_public_head_models


@pytest.fixture
def configured(tmp_path):
    # Deliberately synthetic tetrahedron; never presented as human scientific evidence.
    v = [[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]]
    f = [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]
    packet = dict(
        schema="soma.local-anatomy-view/1",
        status="QC_ONLY_ANATOMY",
        frame="MRI_surface_RAS_m",
        redistribution_permitted=False,
        meshes=[
            dict(vertices_m=v, faces=f, boundary=n) for n in ["inner_skull", "outer_skull", "scalp"]
        ],
        electrodes_m=[[0.02, 0, 0]],
    )
    (tmp_path / "mesh.json").write_text(json.dumps(packet))
    image = nib.Nifti1Image(np.ones((4, 4, 4), dtype=np.float32), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, tmp_path / "mri.nii.gz")
    entries = [
        dict(
            id="m32-fixture-mesh",
            kind="anatomical-model",
            label="Synthetic guard fixture",
            root="r",
            file="mesh.json",
        ),
        dict(
            id="m32-fixture-mri",
            kind="mri",
            label="Synthetic guard fixture",
            root="r",
            file="mri.nii.gz",
        ),
    ]
    return create_app(
        Registry(Configuration(roots={"r": str(tmp_path)}, entries=entries)),
        jobs_root=tmp_path / "jobs",
    )


@pytest.mark.parametrize(
    "optin,ip,headers",
    [
        (False, "127.0.0.1", {}),
        (True, "192.0.2.1", {}),
        (True, "127.0.0.1", {"Forwarded": "for=127.0.0.1"}),
        (True, "127.0.0.1", {"X-Forwarded-For": "127.0.0.1"}),
        (True, "127.0.0.1", {"X-Real-IP": "127.0.0.1"}),
        (True, "127.0.0.1", {"X-Forwarded-Host": "localhost"}),
        (True, "127.0.0.1", {"Origin": "https://evil.example"}),
        (True, "127.0.0.1", {"Origin": "null"}),
    ],
)
def test_private_anatomy_requires_direct_opted_in_loopback(
    configured, monkeypatch, optin, ip, headers
):
    monkeypatch.setenv("SOMA_LOCAL_ANATOMY_VIEWER", "1" if optin else "0")
    with TestClient(configured, base_url="http://127.0.0.1", client=(ip, 50000)) as c:
        for path in [
            "/api/mri-head-models/local/m32-fixture-mesh",
            "/api/volumes/m32-fixture-mri",
            "/api/volumes/m32-fixture-mri/slice",
        ]:
            assert c.get(path, headers=headers).status_code == 403
        r = c.get("/api/mri-head-models", headers=headers)
        if r.status_code == 200:
            assert r.json()["local_views"] == []


def test_explicit_local_operator_gets_allowed_mesh_and_volume(configured, monkeypatch):
    monkeypatch.setenv("SOMA_LOCAL_ANATOMY_VIEWER", "1")
    with TestClient(configured, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as c:
        r = c.get("/api/mri-head-models/local/m32-fixture-mesh")
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
        assert r.json()["redistribution_permitted"] is False
        assert c.get("/api/volumes/m32-fixture-mri").status_code == 200
        assert c.get("/api/volumes/m32-fixture-mri/slice").status_code == 200
        assert len(c.get("/api/mri-head-models").json()["local_views"]) == 2


@pytest.mark.parametrize(
    "key,value",
    [
        ("vertices_m", [[0, 0, 0]]),
        ("path", "/private/image"),
        ("input_sha256", "a" * 64),
        ("affine", [[1]]),
        ("source_sha256", "b" * 64),
    ],
)
def test_public_report_rejects_private_anatomy_even_nested(key, value):
    r = copy.deepcopy(example())
    r["geometry"]["injected"] = {key: value}
    with pytest.raises(ValueError, match="cannot be public|fingerprint"):
        validate_public_head_models(r)


def test_public_report_cannot_upgrade_qc_to_accuracy_or_accept_nan():
    r = example()
    r["full_conductor_accuracy_established"] = True
    with pytest.raises(ValueError, match="QC"):
        validate_public_head_models(r)
    with pytest.raises(ValueError, match="numeric"):
        read_public_head_models(b'{"a": NaN}')


def test_failed_numerical_target_cannot_be_relabelled():
    r = example()
    r["comparisons"][0]["passed"] = True
    with pytest.raises(ValueError, match="relabeling"):
        validate_public_head_models(r)
