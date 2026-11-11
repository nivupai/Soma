"""Read-only protocol preview and CLI boundaries, with no human data."""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from services.explorer_api.app import create_app
from soma.cli import app


def test_preview_does_not_invent_scientific_results(tmp_path):
    with TestClient(create_app(jobs_root=tmp_path / "jobs"), base_url="http://127.0.0.1") as c:
        r = c.get("/api/eeg-benchmarks/demo-eeg-benchmark")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "NOT_RUN"
        assert d["variants"] == []
        assert not d["confirmatory_claim_allowed"]
        assert "historical" in str(d).lower()
        assert c.get("/api/eeg-benchmarks/unconfigured").status_code == 404
        assert c.post("/api/eeg-benchmarks/demo-eeg-benchmark").status_code == 405


def test_focused_cli_exposes_inspection_and_explicit_execution():
    r = CliRunner().invoke(app, ["benchmark", "eeg", "--help"])
    assert r.exit_code == 0
    for command in ["plan", "run", "results", "compare", "verify"]:
        assert command in r.stdout
