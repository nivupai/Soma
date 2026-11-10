"""Explicit cached M21 review; no dataset download, hidden reference or pipeline launch."""

import argparse
import json
import os
from pathlib import Path

import yaml

from soma.core.provenance import sha256
from soma.human.adapters import bids_fmri, eeg, mri
from soma.human.evidence import seal_bundle, write_bundle
from soma.human.model import now
from soma.human.permissions import PermissionEvidence, check_permission
from soma.human.readiness import execution_readiness, session_audit, write_readiness
from soma.human.workflow import freeze_cohort, read_execution, run, template
from soma.protocol.model import Protocol, write_seal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = args.previous.resolve(strict=True)
    out = args.output
    if out.exists():
        raise FileExistsError("Immutable pilot output already exists")
    out.mkdir(parents=True, mode=0o700)
    os.chmod(out, 0o700)
    key = bytes.fromhex(json.loads((previous / "pseudonym-key.local.json").read_text())["key_hex"])
    # Explicit selections fixed before any new outcome/QC inspection.
    cohorts = {
        "eegmmidb": [eeg(Path("data/raw"), s, r, key) for s in (1, 2) for r in (4, 8)],
        "ibsr-v2": [
            mri(Path("data/external/ibsr"), "ibsr-v2", f"IBSR_{s:02}", key) for s in (1, 2)
        ],
        "ds000114": bids_fmri(Path("data/external/ds000114"), "01", key),
    }
    notices = {
        "eegmmidb": previous / "physionet-public-license.html",
        "ibsr-v2": Path("data/external/ibsr/IBSR_nifti_stripped/README.txt"),
        "ds000114": Path("data/external/ds000114/dataset_description.json"),
    }
    results = {}
    reports = {}
    for dataset, selections in cohorts.items():
        permission = PermissionEvidence.from_dict(
            json.loads((previous / (dataset + "-permission.local.json")).read_text())
        )
        source = notices[dataset]
        version = selections[0].identity.document()["version"]
        p = template(dataset, version).document()
        # Restrictive evidence policy is frozen before the extra EEG run is analyzed.
        p["optional_metadata"] = {
            "research_readiness": {
                "schema": "soma.readiness.policy/1.0.0",
                "analysis": "longitudinal-descriptive"
                if dataset in {"eegmmidb", "ds000114"}
                else "existing-descriptive",
                "registration_required": False,
                "chronology_required": dataset in {"eegmmidb", "ds000114"},
            }
        }
        p["version"] = "2.0.0"
        sealed = freeze_cohort(Protocol.from_dict(p), [s.identity for s in selections])
        write_seal(sealed, out / (dataset + "-protocol.local.json"))
        private_entry = {
            "id": "use-notice",
            "kind": "license",
            "sha256": sha256(source),
            "issuer": "local-release-source-not-authenticated",
            "source": "existing-local-release-notice",
            "document_version": None,
            "issued_at": None,
            "valid_from": None,
            "expires_at": None,
            "revoked_at": None,
            "review": {"status": "REQUIRED", "reviewer": None, "reviewed_at": None},
            "purpose": "methods_research",
            "actions": ["metadata", "analyze", "export_aggregate"],
            "distribution": "AGGREGATE_ONLY",
        }
        bundle = seal_bundle(dataset, version, sealed.protocol.fingerprint, [private_entry])
        write_bundle(bundle, out / (dataset + "-evidence.local.json"))
        refs = {"use-notice": (source.parent, source.name)}
        report = execution_readiness(sealed, selections, permission, source, bundle, refs)
        write_readiness(report, out / "readiness" / dataset)
        reports[dataset] = report
        policy = check_permission(
            permission,
            dataset=dataset,
            version=version,
            purpose="methods_research",
            action="analyze",
            source_content=source.read_bytes(),
        )
        results[dataset] = {
            "dataset_scoped_subjects": len({s.identity.participant for s in selections}),
            "recordings_inspected": len(selections),
            "explicit_sessions": len(
                {
                    s.identity.document()["session"]
                    for s in selections
                    if s.identity.document()["session"] is not None
                }
            ),
            "permission_software_policy": policy["status"],
            "new_human_review_evidence": "NOT_AVAILABLE",
            "research_readiness": report["status"],
            "newly_unblocked_records": 0,
        }
        if dataset == "eegmmidb":
            # Existing descriptive analysis is permitted; this is not a longitudinal pass.
            analysis_protocol = freeze_cohort(
                template(dataset, version), [s.identity for s in selections]
            )
            write_seal(analysis_protocol, out / "eeg-descriptive-protocol.local.json")
            execution = run(
                analysis_protocol,
                selections,
                permission,
                source,
                cache=out / "cache/eeg",
                output=out / "eeg-execution",
                sequence=1,
            )
            assert all(s.facts()["events"] == selections[0].facts()["events"] for s in selections)
            comparisons = [
                session_audit(
                    [s.identity for s in selections if s.subject == str(subject)],
                    chronology_required=True,
                )
                for subject in (1, 2)
            ]
            (out / "eeg-session-comparisons.local.json").write_text(
                json.dumps(comparisons, indent=2) + "\n"
            )
            (out / "eeg-qc.local.json").write_text(
                json.dumps(
                    [
                        {
                            "identity": u["identity"],
                            "status": u["status"],
                            "qc": u.get("outcome", {}).get("qc"),
                        }
                        for u in execution["units"]
                    ],
                    indent=2,
                )
                + "\n"
            )
            results[dataset].update(
                existing_descriptive_analyses_complete=sum(
                    u["status"] == "COMPLETE" for u in execution["units"]
                ),
                same_task_event_semantics=True,
                independent_participants=2,
                repeated_relationship="REPEATED_RUN",
                visit_timing_available=False,
                longitudinal_reliability_established=False,
            )
        elif dataset == "ibsr-v2":
            old = read_execution(previous / "executions/ibsr-v2/result.json")
            assert {s.identity.fingerprint for s in selections} == {
                u["identity_fingerprint"] for u in old["units"]
            }
            assert all(u["status"] == "COMPLETE" for u in old["units"])
            for s in selections:
                s.verify_inputs()
            (out / "ibsr-previous-results.local.json").write_text(json.dumps(old, indent=2) + "\n")
            results[dataset].update(
                previous_fixed_prediction_results_reviewed=2,
                new_segmentation_analyses=0,
                CSF_performance="POOR_PRESERVED",
                conductor_model_validation=False,
            )
    # No new authoritative MRBrainS source was provided; no hidden-test or new MRI reads.
    mr = read_execution(previous / "executions/mrbrains13/result.json")
    assert len(mr["units"]) == 5 and all(u["status"] == "BLOCKED" for u in mr["units"])
    results["mrbrains13"] = {
        "dataset_scoped_subjects": 5,
        "records_retained": 5,
        "blocked": 5,
        "new_authoritative_permission_source": "NOT_AVAILABLE",
        "research_readiness": "BLOCKED",
        "newly_unblocked_records": 0,
        "new_MRI_or_hidden_test_payload_reads": False,
        "partition": "previously inspected training, not fresh holdout",
    }
    # Search only roots named by the existing preprocessing plan, with bounded symlink guards.
    cfg = yaml.safe_load(Path("configs/fmri-preprocessing-plan.yaml").read_text())
    roots = [Path(cfg["raw"]) / "derivatives", Path(cfg["output"])]
    from soma.human.preprocessing import validate_root

    derivative_counts = {}
    for index, root in enumerate(roots):
        if root.exists():
            validate_root(root)
            derivative_counts[str(index)] = sum(
                p.is_file() for p in root.rglob("*desc-preproc_bold.nii*")
            )
        else:
            derivative_counts[str(index)] = 0
    if any(derivative_counts.values()):
        raise RuntimeError("Derivatives found; explicit manifest and full audit required")
    gaps = {
        "schema": "soma.preprocessing.gaps/1.0.0",
        "dataset": "ds000114",
        "status": "NOT_AVAILABLE",
        "configured_derivative_roots_checked": len(roots),
        "derivative_BOLD_candidates": sum(derivative_counts.values()),
        "missing": [
            "pipeline execution/version/configuration/environment receipts",
            "source snapshot and current BIDS validation",
            "preprocessed BOLD/masks and source anatomical correspondence",
            "complete directed ITK transforms and common-space evidence",
            "measured motion, FD, DVARS, nonsteady-state indicators and definitions",
            "SDC method/justification",
            "reviewed anatomical/functional QC reports",
            "acquisition chronology and reviewed longitudinal task correspondence",
        ],
        "handoff_configuration": "configs/fmri-preprocessing-plan.yaml",
        "pipeline_run": False,
        "new_human_inference": False,
    }
    (out / "ds000114-gaps.local.json").write_text(json.dumps(gaps, indent=2) + "\n")
    results["ds000114"].update(
        preprocessing_status="NOT_AVAILABLE",
        configured_derivative_roots_checked=2,
        derivative_BOLD_candidates=0,
        blocked_sessions=2,
        new_human_GLMs=0,
    )
    (out / "coverage.json").write_text(
        json.dumps(
            {
                "reviewed_at": now(),
                "datasets": results,
                "actual_verified_external_registrations": 0,
                "newly_unblocked_records": 0,
                "large_downloads_or_external_pipeline_execution": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
