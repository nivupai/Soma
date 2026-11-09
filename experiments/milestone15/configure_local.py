"""Explicit opt-in verification setup for already cached, permitted resources.

Writes only an ignored local allowlist; never downloads data or modifies reports.
"""

import json
from pathlib import Path


def main() -> None:
    root = Path.cwd()
    eeg = sorted((root / "data/raw").rglob("*R04.edf"))[0]
    effect = next((root / "reports/milestone13-synthetic").rglob("*effect_size.nii.gz"))
    entries = [
        {
            "id": "local-eeg",
            "kind": "eeg",
            "label": "EEGBCI · cached motor imagery",
            "root": "eeg",
            "file": str(eeg.relative_to(root / "data/raw")),
            "run": "4",
            "provenance": "Permitted cached PhysioNet EEGBCI recording; raw, as-recorded reference",
        },
        {
            "id": "local-mri",
            "kind": "mri",
            "label": "ds000114 · cached T1w",
            "root": "mri",
            "file": "sub-01/ses-test/anat/sub-01_ses-test_T1w.nii.gz",
            "session": "test",
            "frame": "ds000114-native-RAS",
            "units": "scanner intensity",
            "provenance": "Public ds000114 permitted local subset; no registration certification",
        },
        {
            "id": "local-source",
            "kind": "source",
            "label": "Template source recovery · existing artifact",
            "root": "reports",
            "file": "source-simulation-final/example-recovery.npz",
            "geometry": "source-simulation-final/geometry.npz",
            "surface": "fsaverage/bem/soma-ico3-white-src.fif",
            "surface_root": "anatomy",
            "synthetic": True,
            "operators": "source-simulation-final/simulation-operators.npz",
            "metadata_file": "source-simulation-final/forward.json",
            "manifest": "source-simulation-final/manifest.json",
            "frame": "MNE-head",
            "units": "A m",
            "provenance": "fsaverage template; simulated currents/noise; not participant-matched",
        },
        {
            "spatial_units_override": "mm",
            "id": "local-fmri",
            "kind": "fmri",
            "label": "Synthetic task effect · historical artifact",
            "root": "reports",
            "file": str(effect.relative_to(root / "reports")),
            "synthetic": True,
            "frame": "synthetic-RAS",
            "units": "BOLD effect units",
            "provenance": "Milestone13 synthetic effect map; descriptive under14.1",
        },
        {
            "id": "local-calibration",
            "kind": "experiment",
            "label": "Null calibration audit · Milestone14.1",
            "root": "reports",
            "file": "milestone141-null-audit/summary.json",
            "synthetic": True,
            "manifest": "milestone141-null-audit/manifest.json",
            "figures": ["milestone141-null-audit/null-marginal-family.png"],
            "compatibility": {
                "units": "probability",
                "estimand": "multi_condition_null_calibration",
                "frame": "nonspatial",
                "processing": "M14.1-frozen-protocol",
            },
            "provenance": "Recorded synthetic calibration; no human inference certification",
        },
    ]
    entries.append(
        {
            "id": "local-source-validation",
            "kind": "experiment",
            "label": "Template inverse recovery and regularization",
            "root": "reports",
            "file": "source-simulation-final/summary.json",
            "synthetic": True,
            "manifest": "source-simulation-final/manifest.json",
            "figures": [
                "source-simulation-final/regularization-tradeoff.png",
                "source-simulation-final/synthetic-recovery.png",
            ],
            "compatibility": {
                "units": "mixed; see metrics",
                "estimand": "source_recovery",
                "frame": "MNE-head",
                "processing": "sealed-template-source-simulation",
            },
            "provenance": "Template inverse simulation; not participant-matched anatomical truth",
        }
    )
    config = {
        "roots": {
            "eeg": str(root / "data/raw"),
            "mri": str(root / "data/external/ds000114"),
            "reports": str(root / "reports"),
            "anatomy": str(root / "data/anatomy"),
        },
        "entries": entries,
    }
    Path("configs/explorer.local.json").write_text(json.dumps(config, indent=2) + "\n")
    print(
        "Configured four cached scientific resources and two synthetic experiments; no downloads."
    )


if __name__ == "__main__":
    main()
