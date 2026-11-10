"""New API views consume existing native metadata only; no science/provider work on GET."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.human.readiness import execution_readiness, write_readiness
from tests.readiness.test_sessions_gates import prepared


def test_demo_readiness_has_blocked_requirements_and_no_execution(tmp_path):
    with (
        patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("science")),
        patch(
            "soma.human.registration.OSFAttachments.retrieve_attachment",
            side_effect=AssertionError("network"),
        ),
    ):
        with TestClient(
            create_app(Registry(Configuration()), tmp_path), base_url="http://127.0.0.1"
        ) as c:
            d = c.get("/api/human-audits/demo-human-audit").json()
            assert d["status"] == "NOT_RUN" and d["readiness"]["status"] == "BLOCKED"
            assert not d["registration"]["external_preregistration_verified"]
            assert {g["status"] for g in d["readiness"]["gates"]} == {
                "BLOCKED",
                "INDETERMINATE",
                "NOT_APPLICABLE",
            }


def test_explicit_native_readiness_never_becomes_current_authorization(tmp_path):
    args = prepared(tmp_path, review="REQUIRED")
    r = execution_readiness(*args)
    write_readiness(r, tmp_path / "native")
    registry = Registry(
        Configuration(
            roots={"allowed": str(tmp_path)},
            entries=[
                Entry(
                    id="local-readiness",
                    kind="human-readiness",
                    label="Synthetic test receipt",
                    root="allowed",
                    file="native/result.json",
                )
            ],
        )
    )
    with TestClient(create_app(registry, tmp_path / "api"), base_url="http://127.0.0.1") as c:
        response = c.get("/api/human-audits/local-readiness")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "BLOCKED"
        assert d["registration"]["status"] == "HISTORICAL_RECEIPT_NOT_REVALIDATED"
        assert not d["registration"]["external_preregistration_verified"]
        assert str(tmp_path) not in response.text and "fictional-issuer" not in response.text
        assert d["units"][0]["status"] == "NOT_EXECUTED"


def test_thirteenth_sdk_example_is_fictional_and_offline():
    from examples.research_readiness import run

    result = run()
    assert result["synthetic_only"] and not result["actual_human_data_accessed"]
    assert not result["actual_external_attestation"]
    assert result["registration_status"] == "UNVERIFIED"


def test_cli_commands_remain_offline_and_cannot_dispatch_shell(tmp_path):
    import json

    from typer.testing import CliRunner

    from soma.cli import app
    from soma.human.evidence import write_bundle

    args = prepared(tmp_path)
    bundle = args[4]
    path = tmp_path / "bundle.local.json"
    write_bundle(bundle, path)
    refs = tmp_path / "references.local.json"
    refs.write_text(json.dumps({"notice": {"root": str(tmp_path), "path": "notice.txt"}}))
    runner = CliRunner()
    result = runner.invoke(app, ["evidence", "verify", str(path), str(refs)])
    assert result.exit_code == 0 and json.loads(result.stdout)["status"] == "READY"
    for command in [
        ["registration", "verify-attachment"],
        ["preprocessing", "audit"],
        ["research", "readiness"],
        ["sessions", "validate"],
    ]:
        result = runner.invoke(app, [*command, "--help"])
        assert result.exit_code == 0
    assert str(tmp_path) not in runner.invoke(app, ["evidence", "inspect", str(path)]).stdout
