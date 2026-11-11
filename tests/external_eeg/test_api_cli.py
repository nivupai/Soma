"""Read-only blocked evidence and real Typer planning/execution without EEG."""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from services.explorer_api.app import create_app
from soma.cli import app


def test_api_never_executes_or_invents_human_scores(tmp_path):
    with TestClient(create_app(jobs_root=tmp_path / "jobs"), base_url="http://127.0.0.1") as c:
        response = c.get("/api/external-eeg/demo-external-eeg")
        assert response.status_code == 200
        d = response.json()
        assert d["status"] == "BLOCKED" and d["performance"] == []
        assert not d["model_compatibility"]["original_m22_model_available"]
        assert c.post("/api/external-eeg/demo-external-eeg").status_code == 405
        assert c.get("/api/external-eeg/not-configured").status_code == 404


def test_cli_seals_missing_cohort_and_preserves_blocker_receipt(tmp_path):
    runner = CliRunner()
    root = tmp_path / "raw"
    root.mkdir()
    p = runner.invoke(app, ["benchmark", "external", "plan", str(root), str(tmp_path / "plan")])
    assert p.exit_code == 0, p.stdout
    assert "SEALED_BEFORE_OUTCOMES" in p.stdout
    r = runner.invoke(
        app,
        ["benchmark", "external", "run", str(root), str(tmp_path / "plan"), str(tmp_path / "run")],
    )
    assert r.exit_code == 0, r.stdout
    assert "BLOCKED" in r.stdout
    v = runner.invoke(app, ["benchmark", "external", "verify", str(tmp_path / "run/result.json")])
    assert v.exit_code == 0 and "VERIFIED" in v.stdout
