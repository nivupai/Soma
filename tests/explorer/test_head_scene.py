"""M35 synthetic head scene and mock uncertainty overlay contracts; no human data."""

import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.explorer_api.app import create_app
from services.explorer_api.head_scene import (
    DEMO_HEAD_ID,
    HeadScene,
    SourceUncertaintyOverlay,
    demo_head_scene,
    demo_uncertainty_overlay,
    icosphere,
)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(jobs_root=tmp_path / "jobs"), base_url="http://127.0.0.1") as c:
        yield c


def test_demo_head_scene_is_synthetic_nested_and_not_anatomically_validated(client):
    listing = client.get("/api/head-scenes").json()
    assert listing == [
        dict(
            head_id=DEMO_HEAD_ID,
            label="Synthetic concentric-shell head",
            synthetic=True,
            readiness="NOT_READY",
        )
    ]
    response = client.get(f"/api/head-scenes/{DEMO_HEAD_ID}")
    assert response.status_code == 200
    scene = response.json()
    assert scene["contract"] == "soma.explorer.head-scene/1"
    assert scene["synthetic"] and scene["redistributable"]
    assert scene["private_mri_used"] is False
    assert [layer["name"] for layer in scene["layers"]] == [
        "scalp",
        "outer_skull",
        "inner_skull",
        "cortex",
    ]
    # Geometric validity and anatomical validation are reported separately.
    assert scene["geometrically_valid"] is True
    assert scene["anatomically_validated"] is False
    assert scene["readiness"] == "NOT_READY"
    assert scene["readiness_status"] == "NOT_READY_FOR_FORWARD_MODEL"
    assert "missing MRI origin or local-use authorization" in scene["readiness_reasons"]
    assert scene["geometry_checks"]["minimum_layer_gap_mm"] > 0
    assert len(scene["sensors"]) == 20
    sources = scene["sources"]
    assert sources["kind"] == "cortical_surface"
    assert len(sources["positions_mm"]) == len(sources["scalar"]) == 162


def test_uncertainty_overlay_is_an_explicit_mock_aligned_with_sources(client):
    overlay = client.get(f"/api/head-scenes/{DEMO_HEAD_ID}/uncertainty").json()
    assert overlay["contract"] == "soma.explorer.source-uncertainty-overlay/1"
    assert overlay["origin"] == "MOCK_FIXTURE" and overlay["fixture"] is True
    assert overlay["units"] == "mm" and overlay["confidence_level"] == 0.95
    assert overlay["n_sources"] == len(demo_head_scene().sources.positions_mm)
    assert all(
        lo <= m <= hi
        for lo, m, hi in zip(overlay["lower"], overlay["mean"], overlay["upper"], strict=True)
    )
    assert any("MOCK FIXTURE" in w for w in overlay["warnings"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/head-scenes/m32-anything",
        "/api/head-scenes/participant-01",
        "/api/head-scenes/participant-01/uncertainty",
        "/api/head-scenes/..%2Fdata",
    ],
)
def test_only_the_synthetic_head_is_served(client, path):
    assert client.get(path).status_code in {403, 404}


def test_private_anatomy_guard_still_applies_to_m32_identities(client, monkeypatch):
    monkeypatch.setenv("SOMA_LOCAL_ANATOMY_VIEWER", "0")
    assert client.get("/api/head-scenes/m32-fixture").status_code == 403


def test_overlay_contract_rejects_inverted_or_misaligned_intervals():
    good = demo_uncertainty_overlay().model_dump()
    bad = copy.deepcopy(good)
    bad["lower"][0] = bad["mean"][0] + 1
    with pytest.raises(ValidationError):
        SourceUncertaintyOverlay.model_validate(bad)
    short = copy.deepcopy(good)
    short["upper"] = short["upper"][:-1]
    with pytest.raises(ValidationError):
        SourceUncertaintyOverlay.model_validate(short)
    mislabelled = copy.deepcopy(good)
    mislabelled["origin"] = "M34_RESULT"
    with pytest.raises(ValidationError):
        SourceUncertaintyOverlay.model_validate(mislabelled)


def test_head_scene_contract_refuses_anatomical_upgrade_of_synthetic_geometry():
    value = demo_head_scene().model_dump()
    value["anatomically_validated"] = True
    with pytest.raises(ValidationError):
        HeadScene.model_validate(value)
    value["readiness"] = "VALIDATED"
    with pytest.raises(ValidationError):
        HeadScene.model_validate(value)


def test_icosphere_is_closed_and_unit():
    vertices, faces = icosphere(2)
    assert vertices.shape == (162, 3) and faces.shape == (320, 3)
    assert np.allclose(np.linalg.norm(vertices, axis=1), 1)


def test_openapi_documents_head_scene_contracts(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {"HeadScene", "SourceUncertaintyOverlay", "GeometryChecks"} <= set(schemas)
