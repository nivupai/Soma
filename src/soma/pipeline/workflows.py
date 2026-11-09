"""Cohort orchestration, reference comparisons and QC aggregation."""

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from soma.anatomy.reporting import AnatomyReport
from soma.benchmarks.segmentation import LabelVolume, score
from soma.core.provenance import sha256, write_json
from soma.datasets.external_anatomy import TISSUES
from soma.datasets.human_mri import load_human, mapped_reference
from soma.imaging.nifti import load_nifti
from soma.pipeline.derivatives import private_output, validate_derivatives
from soma.pipeline.engine import configuration, run_pipeline
from soma.pipeline.ingestion import legacy_records
from soma.validation.cohort import subject_interval


def run_legacy(
    dataset: str,
    data_root: Path,
    config: dict[str, Any],
    output: Path,
    *,
    resume: bool = False,
    dry_run: bool = False,
    report_root: Path | None = None,
) -> dict[str, Any]:
    ibsr = data_root if dataset == "ibsr" else Path("data/external/ibsr")
    mrbrains = data_root if dataset == "mrbrains" else Path("data/external/mrbrains")
    records = legacy_records(ibsr, mrbrains, dataset=dataset)
    reports = report_root or output / "soma-reports"
    derivatives = output / "derivatives/soma"
    rows = []
    failures = []
    for record in records:
        try:
            rows.append(
                run_pipeline(
                    record, config, derivatives, report_root=reports, resume=resume, dry_run=dry_run
                )
            )
        except (ValueError, OSError, RuntimeError) as exc:
            failures.append({"subject": record.subject, "diagnostic": str(exc)})
    return {
        "status": "dry-run" if dry_run else "complete" if rows and not failures else "incomplete",
        "subjects": len(records),
        "completed": len(rows),
        "failures": failures,
        "cache_hits": sum(r.get("cache_hits", 0) for r in rows),
        "runs": rows,
    }


def qc_reports(source: Path, output: Path) -> dict[str, Any]:
    private_output(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for p in source.rglob("run.json"):
        r = json.loads(p.read_text())
        rows.append(
            {
                "run": str(p.parent),
                "status": r["status"],
                "numerical": r.get("qc", {}).get("numerical_status", "INDETERMINATE"),
                "anatomical": "INDETERMINATE",
                "failed_stage": r.get("failed_stage"),
            }
        )
    # Derivative-only roots have sidecars but no custom run journals.
    if not rows:
        for p in source.rglob("*dseg.json"):
            r = json.loads(p.read_text())
            rows.append(
                {
                    "derivative": str(p),
                    "run_identity": r.get("Soma", {}).get("RunIdentity"),
                    "numerical": "INDETERMINATE",
                    "anatomical": "INDETERMINATE",
                    "reason": "Run journal not in derivative dataset; use separate Soma reports",
                }
            )
    if not rows:
        raise ValueError("No Soma QC run journals or derivative sidecars found")
    result = {"records": rows, "anatomical_certification": False}
    write_json(output / "qc-summary.json", result)
    return result


def benchmark_pipeline(config_path: Path, output: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text())
    seal = json.loads(Path("configs/milestone12-freeze.json").read_text())
    for name, h in seal["files_sha256"].items():
        if sha256(Path(name)) != h:
            raise ValueError("M12 frozen benchmark/protocol mismatch")
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    pipeline_cfg = configuration(Path(cfg["pipeline_config"]))
    result = {}
    validation = {}
    failures = []
    timing = {}
    for dataset in ["ibsr", "mrbrains"]:
        records = legacy_records(
            Path(cfg["ibsr_root"]), Path(cfg["mrbrains_root"]), dataset=dataset
        )
        rows = []
        runs = []
        started = time.perf_counter()
        for record in records:
            try:
                assert record.legacy is not None
                run = run_pipeline(
                    record,
                    pipeline_cfg,
                    output / dataset / "derivatives/soma",
                    report_root=output / dataset / "reports",
                )
                runs.append(run)
                native = load_human(
                    Path(record.legacy["reference"]),
                    dataset=record.legacy["dataset"],
                    subject=record.legacy["subject"],
                    role="labels",
                )
                reference, valid = mapped_reference(native, record.legacy["dataset"])
                labels_path = next(
                    (
                        output / dataset / "derivatives/soma" / ("sub-" + record.subject) / "anat"
                    ).glob("*dseg.nii.gz")
                )
                predicted = load_nifti(labels_path, kind="labels")
                sid = record.legacy["subject"]
                ontology = TISSUES
                space = sid + "-native"
                metrics = score(
                    LabelVolume(
                        predicted,
                        sid,
                        space,
                        ontology,
                        {"backend": "Soma multi-Otsu", "reference_used": False},
                    ),
                    LabelVolume(
                        reference, sid, space, ontology, {"source": "provided manual annotations"}
                    ),
                    valid_mask=valid if dataset == "mrbrains" else None,
                )
                rows.append(metrics)
            except (ValueError, OSError, RuntimeError) as exc:
                failures.append({"subject": record.subject, "diagnostic": str(exc)})
        elapsed = time.perf_counter() - started
        prior_path = (
            Path(cfg["prior_results_root"])
            / ("development" if dataset == "ibsr" else "external")
            / "subject-results.json"
        )
        prior = json.loads(prior_path.read_text())["subjects"]
        previous = {r["subject"]: r for r in prior}
        differences = []
        for row in rows:
            for a, b in zip(row["labels"], previous[row["subject"]]["labels"], strict=True):
                differences.append(
                    {
                        key: float(a[key] - b[key])
                        for key in [
                            "Dice",
                            "Jaccard",
                            "ASSD_mm",
                            "HD95_mm",
                            "signed_volume_error_mm3",
                        ]
                        if a[key] is not None and b[key] is not None
                    }
                )
        write_json(
            output / (dataset + "-subject-metrics.json"),
            {"subjects": rows, "differences_from_frozen_baseline": differences},
        )
        flat = [
            {"subject": r["subject"], **{k: v for k, v in t.items() if k != "boundaries"}}
            for r in rows
            for t in r["labels"]
        ]
        pd.DataFrame(flat).to_csv(output / (dataset + "-metrics.csv"), index=False)
        resumed = []
        resume_start = time.perf_counter()
        for record in records:
            resumed.append(
                run_pipeline(
                    record,
                    pipeline_cfg,
                    output / dataset / "derivatives/soma",
                    report_root=output / dataset / "reports",
                    resume=True,
                )
            )
        timing[dataset] = {
            "initial_wall_s": elapsed,
            "verified_resume_wall_s": time.perf_counter() - resume_start,
            "first_stage_hits": sum(r["cache_hits"] for r in runs),
            "resume_verified_runs": sum(r.get("resume_verified", False) for r in resumed),
        }
        result[dataset] = {
            "completed": len(rows),
            "expected": 18 if dataset == "ibsr" else 5,
            "macro_Dice": subject_interval([r["macro_Dice"] for r in rows], seed=cfg["seed"])
            if rows
            else None,
            "max_absolute_baseline_difference": max(
                (abs(x) for d in differences for x in d.values()), default=None
            ),
            "qc_anatomical": "INDETERMINATE",
        }
        validation[dataset] = validate_derivatives(output / dataset / "derivatives/soma")
    write_json(output / "derivative-validation.json", validation)
    from soma.pipeline.plots import benchmark_figures

    benchmark_figures(output, result, timing)
    return report.finish(
        {
            "status": "complete"
            if not failures and all(x["completed"] == x["expected"] for x in result.values())
            else "incomplete",
            "datasets": result,
            "failures": failures,
            "performance": timing,
            "derivative_validation": validation,
            "external_evaluation_status": "previously inspected training subjects; "
            "not a fresh holdout",
            "BEM_readiness": "INDETERMINATE",
        }
    )
