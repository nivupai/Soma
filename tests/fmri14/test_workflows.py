"""Missing real assets cannot produce fabricated pilot/cohort completion."""

import json

import pytest
import yaml
from typer.testing import CliRunner

from soma.cli import app
from soma.fmri.audit_workflows import audit_workflow, cohort_retest, pilot_retest
from soma.fmri.fmriprep import external_preprocessing


def configs(tmp_path):
    audit = tmp_path / "audit.yaml"
    audit.write_text(
        yaml.safe_dump(
            {
                "raw": str(tmp_path / "raw"),
                "preprocessed": str(tmp_path / "absent"),
                "subject": "01",
                "sessions": ["test", "retest"],
                "task": "fingerfootlips",
                "space": "T1w",
            }
        )
    )
    pilot = tmp_path / "pilot.yaml"
    pilot.write_text(yaml.safe_dump({"audit_config": str(audit), "subjects": ["01"]}))
    return audit, pilot


def test_missing_audit_and_dry_run_never_fit(tmp_path):
    audit, _ = configs(tmp_path)
    output = tmp_path / "dry"
    r = audit_workflow(audit, output, dry_run=True)
    assert r["status"] == "dry-run" and not output.exists()
    r = audit_workflow(audit, tmp_path / "audit")
    assert r["eligible_sessions"] == 0 and r["raw_models_fitted"] == 0
    assert r["status"] == "unavailable"


def test_pilot_unavailable_and_wrong_identity(tmp_path):
    audit, pilot = configs(tmp_path)
    r = pilot_retest(pilot, tmp_path / "pilot")
    assert not r["real_test_retest_completed"] and r["subjects_completed"] == 0
    spec = yaml.safe_load(pilot.read_text())
    spec["subjects"] = ["02"]
    pilot.write_text(yaml.safe_dump(spec))
    with pytest.raises(ValueError, match="subject"):
        pilot_retest(pilot, tmp_path / "wrong")


def test_cohort_requires_pilot_and_preserves_missingness(tmp_path):
    config = tmp_path / "cohort.yaml"
    config.write_text(
        yaml.safe_dump({"subjects": ["01", "02"], "pilot_receipt": str(tmp_path / "absent.json")})
    )
    r = cohort_retest(config, tmp_path / "cohort")
    assert r["subjects_attempted"] == 0 and not r["cohort_downloaded"]
    receipt = tmp_path / "pilot.json"
    receipt.write_text(json.dumps({"status": "unavailable"}))
    config.write_text(yaml.safe_dump({"subjects": ["01"], "pilot_receipt": str(receipt)}))
    r = cohort_retest(config, tmp_path / "stale")
    assert r["subjects_completed"] == 0


def test_external_execution_never_installs_or_runs_implicitly(tmp_path, monkeypatch):
    import soma.fmri.fmriprep as module

    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    r = external_preprocessing(
        tmp_path,
        tmp_path / "output",
        subject="01",
        template_cache=tmp_path / "templates",
        work=tmp_path / "work",
    )
    assert r["available"] is False and r["execute_requested"] is False
    assert not (tmp_path / "output").exists()
    with pytest.raises(ValueError, match="Installed"):
        external_preprocessing(
            tmp_path,
            tmp_path / "output",
            subject="01",
            template_cache=tmp_path / "templates",
            work=tmp_path / "work",
            execute=True,
        )


@pytest.mark.parametrize("command", ["audit-preproc", "pilot-retest", "cohort-retest"])
def test_cli_dry_run_is_explicit(tmp_path, command):
    audit, pilot = configs(tmp_path)
    config = audit if command == "audit-preproc" else pilot
    if command == "cohort-retest":
        config = tmp_path / "cohort.yaml"
        config.write_text('subjects: ["01"]\n')
    r = CliRunner().invoke(
        app,
        ["fmri", command, "--config", str(config), "--output", str(tmp_path / "dry"), "--dry-run"],
    )
    assert r.exit_code == 0, r.stdout
    assert "dry-run" in r.stdout and not (tmp_path / "dry").exists()
