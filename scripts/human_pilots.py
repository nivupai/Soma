"""Explicit local pilot invocation; no dataset download and no hidden test reads."""

import argparse
import json
import os
import secrets
import urllib.request
from pathlib import Path

from soma.human.adapters import bids_fmri, eeg, mri
from soma.human.model import now
from soma.human.permissions import evidence
from soma.human.workflow import freeze_cohort, plan, run, template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refresh-public-license", action="store_true")
    args = parser.parse_args()
    out = args.output
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(out)
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    keyfile = out / "pseudonym-key.local.json"
    if keyfile.exists():
        key = bytes.fromhex(json.loads(keyfile.read_text())["key_hex"])
    else:
        key = secrets.token_bytes(32)

        descriptor = os.open(keyfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"key_hex": key.hex()}, stream)
    license_file = out / "physionet-public-license.html"
    if args.refresh_public_license:
        with urllib.request.urlopen(
            "https://physionet.org/content/eegmmidb/1.0.0/", timeout=30
        ) as response:
            content = response.read(1024**2 + 1)
        if len(content) > 1024**2:
            raise ValueError("License metadata exceeds bound")
        license_file.write_bytes(content)
    inventory = {"reviewed_at": now(), "automatic_dataset_download": False, "datasets": {}}
    roots = {
        "eegmmidb": Path("data/raw"),
        "ibsr-v2": Path("data/external/ibsr"),
        "mrbrains13": Path("data/external/mrbrains"),
        "ds000114": Path("data/external/ds000114"),
    }
    eegbase = roots["eegmmidb"] / "MNE-eegbci-data/files/eegmmidb/1.0.0"
    eeg_subjects = sorted(p.name for p in eegbase.glob("S[0-9][0-9][0-9]") if p.is_dir())
    ibsr_subjects = sorted(
        p.name for p in roots["ibsr-v2"].glob("**/IBSR_[0-9][0-9]") if p.is_dir()
    )
    training = sorted(
        p.parent.name for p in (roots["mrbrains13"] / "training").rglob("LabelsForTraining.nii")
    )
    inventory["datasets"] = {
        "eegmmidb": {"available_subject_directories": len(eeg_subjects)},
        "ibsr-v2": {"available_subject_directories": len(ibsr_subjects)},
        "mrbrains13": {
            "training_subjects": len(training),
            "test_files_names_only": sum(
                p.is_file() for p in (roots["mrbrains13"] / "test").rglob("*")
            ),
            "hidden_test_payload_reads": False,
        },
        "mne-sample": {
            "cached": Path("data/raw/mne-sample/MNE-sample-data/MEG/sample").is_dir(),
            "use_permission": "NOT_ESTABLISHED",
            "analysis": "NOT_REQUESTED",
        },
    }
    cohorts = {
        "eegmmidb": [eeg(roots["eegmmidb"], int(s[1:]), 4, key) for s in eeg_subjects[:2]],
        "ibsr-v2": [mri(roots["ibsr-v2"], "ibsr-v2", s, key) for s in ibsr_subjects[:2]],
        "mrbrains13": [mri(roots["mrbrains13"], "mrbrains13", s, key) for s in training],
        "ds000114": bids_fmri(roots["ds000114"], "01", key),
    }
    notices = {
        "eegmmidb": license_file,
        "ibsr-v2": roots["ibsr-v2"] / "IBSR_nifti_stripped/README.txt",
        "mrbrains13": roots["mrbrains13"] / "Readme.txt",
        "ds000114": roots["ds000114"] / "dataset_description.json",
    }
    results = {}
    for dataset, selections in cohorts.items():
        source = notices[dataset]
        content = source.read_bytes() if source.exists() else b""
        version = selections[0].identity.document()["version"]
        permission = evidence(
            dataset,
            version,
            content,
            source="https://physionet.org/content/eegmmidb/1.0.0/"
            if dataset == "eegmmidb"
            else "local-release-notice",
            license="ODC-By-1.0"
            if dataset == "eegmmidb"
            else "LOCAL-ROHLFING-NOTICE"
            if dataset == "ibsr-v2"
            else "CC0"
            if dataset == "ds000114"
            else "AGREEMENT_NOT_PROVIDED",
            supported=dataset in {"eegmmidb", "ibsr-v2", "ds000114"} and bool(content),
        )
        sealed = freeze_cohort(template(dataset, version), [s.identity for s in selections])
        report = plan(sealed, selections, permission, source)
        (out / (dataset + "-plan.local.json")).write_text(json.dumps(report, indent=2) + "\n")
        permissionfile = out / (dataset + "-permission.local.json")
        permissionfile.write_text(json.dumps(permission.document(), indent=2) + "\n")
        record = run(
            sealed,
            selections,
            permission,
            source,
            cache=out / "cache" / dataset,
            output=out / "executions" / dataset,
            sequence=1,
        )
        results[dataset] = {
            "subjects_inspected": len({s.identity.participant for s in selections}),
            "sessions_explicit": len(
                {
                    s.identity.document()["session"]
                    for s in selections
                    if s.identity.document()["session"] is not None
                }
            ),
            "selected_records": len(selections),
            "eligible_records": sum(
                u["eligibility"]["status"] == "ELIGIBLE" for u in record["units"]
            ),
            "complete_records": sum(u["status"] == "COMPLETE" for u in record["units"]),
            "blocked_or_failed_records": sum(u["status"] != "COMPLETE" for u in record["units"]),
            "permission_status": permission.document()["review_status"],
            "status": record["status"],
            "limitations": sealed.protocol.document()["scientific"]["limitations"],
        }
    (out / "inventory.local.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (out / "aggregate-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
