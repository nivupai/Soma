"""Audit pages are explicit, metadata-only and do not contact external providers."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Registry


def test_human_audit_is_explicit_fixture_and_read_only(tmp_path):
    with (
        patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("GET ran science")),
        patch(
            "soma.human.registration.OSF.retrieve",
            side_effect=AssertionError("GET fetched provider"),
        ),
    ):
        with TestClient(
            create_app(Registry(Configuration()), tmp_path), base_url="http://127.0.0.1"
        ) as c:
            assert len(c.get("/api/human-audits").json()) == 1
            r = c.get("/api/human-audits/demo-human-audit")
            assert r.status_code == 200
            assert r.json()["synthetic"] and r.json()["status"] == "NOT_RUN"
            assert len(r.json()["units"]) == 2
            assert not r.json()["registration"]["external_preregistration_verified"]
            assert c.get("/api/human-audits/not-configured").status_code == 404


def test_public_identity_sdk_example():
    from examples.human_data_audit import run

    assert run() == {
        "synthetic_metadata_only": True,
        "absent_session_preserved": True,
        "dataset_identity_collision_rejected": True,
        "external_preregistration_established": False,
    }
