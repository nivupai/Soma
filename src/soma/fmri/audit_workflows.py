"""Audited imports gate every real model; unavailable derivatives remain visible."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd
import yaml
from bids import BIDSLayout

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import sha256, write_json
from soma.fmri.confounds import configure_confounds
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.fmri.preprocessing_audit import audit_preprocessing, discover_bundle, load_audited_run
from soma.fmri.reliability import cohort_reliability, session_reliability
from soma.pipeline.cache import source_hash
from soma.pipeline.derivatives import private_output


def frozen_protocol() -> None:
    for name in ["configs/milestone14-freeze.json", "configs/milestone14-validation-freeze.json"]:
        seal = json.loads(Path(name).read_text())
        for path, expected in seal["files_sha256"].items():
            if sha256(Path(path)) != expected:
                raise ValueError("Frozen M14 protocol/config mismatch")


def _shape(path: str) -> list[int]:
    image: Any = nib.load(path)
    return list(image.shape)


def inspect_raw(raw: Path, subject: str, task: str) -> dict[str, Any]:
    if not (raw / "dataset_description.json").exists():
        return {"status": "unavailable", "reason": "raw inputs missing"}
    layout = BIDSLayout(raw, validate=False)
    records = []
    for obj in layout.get(
        subject=subject,
        task=task,
        suffix="bold",
        extension=[".nii", ".nii.gz"],
        return_type="object",
    ):
        image: Any = nib.load(obj.path, mmap="r")
        events = layout.get_nearest(
            obj.path,
            suffix="events",
            extension=".tsv",
            strict=True,
            ignore_strict_entities=["suffix", "extension"],
            task=task,
        )
        if not events:
            raise ValueError("Selected raw motor run lacks events")
        table = pd.read_csv(events, sep="\t")
        if set(table.trial_type) != {"Finger", "Foot", "Lips"} or (
            "weight" in table and not np.all(table.weight == 1)
        ):
            raise ValueError("Unexpected motor conditions/modulation; do not substitute EEG labels")
        from soma.fmri.design import validate_events
        from soma.imaging.nifti import load_nifti

        metadata = layout.get_metadata(obj.path)
        validate_events(table, image.shape[3], float(metadata["RepetitionTime"]))
        spatial = load_nifti(Path(obj.path), frame=0)
        records.append(
            {
                "path": obj.path,
                "entities": obj.get_entities(),
                "shape": image.shape,
                "TR_header_s": float(image.header.get_zooms()[3]),
                "metadata": metadata,
                "units": image.header.get_xyzt_units(),
                "geometry": spatial.geometry(),
                "events": table.to_dict("records"),
                "sha256": sha256(Path(obj.path)),
                "events_sha256": sha256(Path(events)),
                "preprocessing": "raw, not modeled",
            }
        )
    t1s = layout.get(
        subject=subject, suffix="T1w", extension=[".nii", ".nii.gz"], return_type="filename"
    )
    return {
        "status": "inspected" if records else "unavailable",
        "description": layout.get_dataset_description(),
        "runs": records,
        "T1w": [
            {
                "path": p,
                "sha256": sha256(Path(p)),
                "shape": _shape(p),
            }
            for p in t1s
        ],
        "current_BIDS_compliance_claimed": False,
        "validation_scope": "legacy BIDS indexing plus explicit acquisition checks",
    }


def audit_workflow(config_path: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    frozen_protocol()
    cfg = yaml.safe_load(config_path.read_text())
    raw = Path(cfg["raw"])
    derivatives = Path(cfg["preprocessed"])
    inspection = inspect_raw(raw, str(cfg["subject"]), cfg["task"])
    if dry_run:
        return {
            "status": "dry-run",
            "raw": inspection,
            "derivative_directory_present": derivatives.is_dir(),
            "no_models_fitted": True,
        }
    private_output(output)
    report = AnatomyReport(output, cfg)
    rows = []
    with report.stage("import_audit"):
        for session in cfg["sessions"]:
            try:
                evidence = cfg.get("evidence", {}).get(session, {})
                if "evidence_json" in cfg:
                    evidence = json.loads(Path(cfg["evidence_json"]).read_text()).get(session, {})
                bundle = discover_bundle(
                    raw,
                    derivatives,
                    subject=str(cfg["subject"]),
                    session=session,
                    task=cfg["task"],
                    space=cfg["space"],
                    run=cfg.get("run"),
                    evidence=evidence,
                )
                receipt = audit_preprocessing(bundle)
                rows.append({"session": session, **receipt})
            except (OSError, ValueError) as exc:
                rows.append(
                    {
                        "session": session,
                        "status": "INDETERMINATE" if isinstance(exc, FileNotFoundError) else "FAIL",
                        "eligible": False,
                        "diagnostic": str(exc),
                    }
                )
    write_json(output / "raw-inspection.json", inspection)
    write_json(output / "audit-sessions.json", rows)
    return report.finish(
        {
            "status": "complete" if all(r["eligible"] for r in rows) else "unavailable",
            "sessions": rows,
            "raw_runs_inspected": len(inspection.get("runs", [])),
            "raw_T1_references": len(inspection.get("T1w", [])),
            "eligible_sessions": sum(r["eligible"] for r in rows),
            "raw_models_fitted": 0,
            "anatomical_certification": False,
            "source_tree_sha256": source_hash(),
        }
    )


def pilot_retest(config_path: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text())
    if dry_run:
        return audit_workflow(Path(cfg["audit_config"]), output, dry_run=True)
    audit_selection = yaml.safe_load(Path(cfg["audit_config"]).read_text())
    if len(cfg["subjects"]) != 1 or str(cfg["subjects"][0]) != str(audit_selection["subject"]):
        raise ValueError("Pilot subject selection disagrees with audit configuration")
    private_output(output)
    report = AnatomyReport(output, cfg, seed=14042)
    audited = audit_workflow(Path(cfg["audit_config"]), output / "audit")
    if audited["status"] != "complete":
        return report.finish(
            {
                "status": "unavailable",
                "subjects_attempted": len(cfg["subjects"]),
                "subjects_completed": 0,
                "reason": "two compatible audited preprocessing sessions unavailable",
                "audit": audited,
                "real_test_retest_completed": False,
                "raw_models_fitted": 0,
                "source_tree_sha256": source_hash(),
            }
        )
    audit_cfg = yaml.safe_load(Path(cfg["audit_config"]).read_text())
    estimates = {}
    motion = []
    receipts = []
    for session in audit_cfg["sessions"]:
        evidence = audit_cfg.get("evidence", {}).get(session, {})
        if "evidence_json" in audit_cfg:
            evidence = json.loads(Path(audit_cfg["evidence_json"]).read_text()).get(session, {})
        bundle = discover_bundle(
            Path(audit_cfg["raw"]),
            Path(audit_cfg["preprocessed"]),
            subject=str(audit_cfg["subject"]),
            session=session,
            task=audit_cfg["task"],
            space=audit_cfg["space"],
            run=audit_cfg.get("run"),
            evidence=evidence,
        )
        receipt = audit_preprocessing(bundle)
        run = load_audited_run(bundle, receipt)
        model = ModelConfig(
            noise_model=cfg["noise_model"],
            smoothing_fwhm=cfg["smoothing_fwhm"],
            hrf_model=cfg.get("hrf_model", "spm"),
            slice_time_ref=float(evidence["slice_time_ref"]),
        )
        configured, qc = configure_confounds(
            run,
            json.loads(bundle.confound_json.read_text()),
            strategy=cfg["confounds"],
            config=model,
        )
        motion.append({"session": session, **qc})
        if not qc["eligible"]:
            return report.finish(
                {
                    "status": "excluded",
                    "subjects_attempted": 1,
                    "subjects_completed": 0,
                    "motion": motion,
                    "real_test_retest_completed": False,
                }
            )
        run = replace(
            run,
            provenance={
                **run.provenance,
                "motion_QC": qc,
                "roi_ontology": "explicit common analysis-mask intersection",
            },
        )
        fitted = fit(run, configured)
        folder = output / session
        folder.mkdir()
        fitted.design.to_csv(folder / "design.tsv", sep="\t", index_label="time_s")
        write_json(
            folder / "model.json",
            {
                "config": asdict(configured),
                "diagnostics": fitted.diagnostics,
                "audit_identity": receipt["identity"],
            },
        )
        for name, weights in cfg["contrasts"].items():
            estimate = contrast(fitted, Contrast(name, weights))
            estimates[(session, name)] = estimate
            for key, image in estimate.maps.items():
                nib.save(image, folder / (name + "_" + key + ".nii.gz"))
            write_json(folder / (name + ".json"), estimate.metadata)
        receipts.append(receipt)
    comparisons = {
        name: session_reliability(
            estimates[(audit_cfg["sessions"][0], name)], estimates[(audit_cfg["sessions"][1], name)]
        )
        for name in cfg["contrasts"]
    }
    write_json(output / "session-reliability.json", comparisons)
    return report.finish(
        {
            "status": "complete",
            "subjects_attempted": 1,
            "subjects_completed": 1,
            "comparisons": comparisons,
            "motion": motion,
            "audit_identities": [r["identity"] for r in receipts],
            "source_tree_sha256": source_hash(),
            "real_test_retest_completed": True,
            "ICC": "not estimated from one participant",
        }
    )


def cohort_retest(config_path: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text())
    receipt_path = Path(cfg.get("pilot_receipt", "reports/milestone14-pilot/summary.json"))
    if dry_run:
        return {
            "status": "dry-run",
            "subjects_requested": len(cfg["subjects"]),
            "gate": "successful current-source pilot required",
            "no_downloads": True,
        }
    private_output(output)
    report = AnatomyReport(output, cfg)
    if not receipt_path.exists():
        return report.finish(
            {
                "status": "unavailable",
                "subjects_requested": len(cfg["subjects"]),
                "subjects_attempted": 0,
                "subjects_completed": 0,
                "reason": "pilot receipt absent",
                "cohort_downloaded": False,
            }
        )
    pilot = json.loads(receipt_path.read_text())
    if (
        pilot.get("status") != "complete"
        or not pilot.get("real_test_retest_completed")
        or pilot.get("source_tree_sha256") != source_hash()
    ):
        return report.finish(
            {
                "status": "unavailable",
                "subjects_requested": len(cfg["subjects"]),
                "subjects_attempted": 0,
                "subjects_completed": 0,
                "reason": "pilot unavailable, excluded or stale",
                "cohort_downloaded": False,
            }
        )
    try:
        manifest = json.loads((receipt_path.parent / "manifest.json").read_text())
        for name, digest in manifest["outputs_sha256"].items():
            if sha256(receipt_path.parent / name) != digest:
                raise ValueError("Pilot output hash mismatch")
        sessions = json.loads((receipt_path.parent / "audit/audit-sessions.json").read_text())
        for session in sessions:
            for name, digest in session["fingerprints"].items():
                if sha256(Path(name)) != digest:
                    raise ValueError("Pilot preprocessing input changed")
    except (OSError, ValueError, KeyError):
        return report.finish(
            {
                "status": "unavailable",
                "subjects_requested": len(cfg["subjects"]),
                "subjects_attempted": 0,
                "subjects_completed": 0,
                "reason": "pilot provenance unavailable or hashes stale",
                "cohort_downloaded": False,
            }
        )
    # Require explicit per-subject import configurations; no implicit expansion/fetch.
    subjects = cfg.get("subject_configs", {})
    outcomes = []
    failures = []
    for subject in cfg["subjects"]:
        if subject not in subjects:
            failures.append({"subject": subject, "reason": "explicit import config unavailable"})
            continue
        selected = yaml.safe_load(Path(subjects[subject]).read_text())
        if list(map(str, selected.get("subjects", []))) != [subject]:
            failures.append({"subject": subject, "reason": "pilot config subject mismatch"})
            continue
        result = pilot_retest(Path(subjects[subject]), output / ("sub-" + subject))
        outcomes.append({"subject": subject, "result": result})
    table: list[dict[str, Any]] = []
    for row in outcomes:
        if row["result"]["status"] != "complete":
            continue
        primary = yaml.safe_load(Path(subjects[row["subject"]]).read_text())["primary"]
        comparison = row["result"]["comparisons"][primary]
        table.extend(
            {"subject": row["subject"], "session": session, "effect": effect}
            for session, effect in zip(
                comparison["sessions"], comparison["ROI_mean_effects"], strict=True
            )
        )
    population = (
        cohort_reliability(pd.DataFrame(table))
        if len(table) >= 10
        else {"status": "INDETERMINATE", "reason": "fewer than5 complete subjects"}
    )
    return report.finish(
        {
            "status": "complete"
            if not failures
            and len(outcomes) == len(cfg["subjects"])
            and all(o["result"]["status"] == "complete" for o in outcomes)
            else "incomplete",
            "subjects_requested": len(cfg["subjects"]),
            "subjects_attempted": len(outcomes),
            "subjects_completed": len(table) // 2,
            "missing_or_failed": failures,
            "outcomes": outcomes,
            "ROI_reliability": population,
            "cohort_downloaded": False,
        }
    )


def sensitivity_workflow(
    config_path: Path, output: Path, *, dry_run: bool = False
) -> dict[str, Any]:
    request = yaml.safe_load(config_path.read_text())
    primary = yaml.safe_load(Path(request["source"]).read_text())
    if dry_run:
        return {
            "status": "dry-run",
            "one_factor": request["one_factor"],
            "select_best": False,
            "no_downloads": True,
        }
    private_output(output)
    report = AnatomyReport(output, request)
    preflight = audit_workflow(Path(primary["audit_config"]), output / "audit")
    if preflight["status"] != "complete":
        return report.finish(
            {
                "status": "unavailable",
                "settings_requested": request["one_factor"],
                "settings_fitted": 0,
                "reason": "audited preprocessing unavailable",
                "raw_models_fitted": 0,
            }
        )
    variants: dict[str, dict[str, Any]] = {
        "expanded-motion": {"confounds": "expanded"},
        "compcor": {"confounds": "compcor"},
        "fd-spikes": {"confounds": "fd-spikes"},
        "ols": {"noise_model": "ols"},
        "ar2": {"noise_model": "ar2"},
        "hrf-derivative": {"hrf_model": "spm + derivative"},
        "no-smoothing": {"smoothing_fwhm": 0.0},
    }
    directory = output / "requests"
    directory.mkdir()
    results = []
    for setting in ["primary", *request["one_factor"]]:
        if setting != "primary" and setting not in variants:
            raise ValueError("Unsupported one-factor sensitivity")
        spec = {**primary, **variants.get(setting, {})}
        path = directory / (setting + ".yaml")
        path.write_text(yaml.safe_dump(spec))
        results.append({"setting": setting, "result": pilot_retest(path, output / setting)})
    return report.finish(
        {
            "status": "complete"
            if all(r["result"]["status"] == "complete" for r in results)
            else "incomplete",
            "results": results,
            "select_best": False,
        }
    )
