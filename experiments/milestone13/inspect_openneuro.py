"""Metadata only: GitHub trees/JSON/README, never fetch functional volumes or labels."""

import json
import urllib.request
from pathlib import Path

from soma.core.provenance import sha256, write_json


def main() -> None:
    root = Path("data/derived/milestone13/openneuro-metadata")
    root.mkdir(parents=True, exist_ok=False)
    summary = {}
    for dataset in ["ds000114", "ds000117"]:
        directory = root / dataset
        directory.mkdir()
        urls = {
            "tree.json": f"https://api.github.com/repos/OpenNeuroDatasets/{dataset}/git/trees/master?recursive=1",
            "dataset_description.json": f"https://raw.githubusercontent.com/OpenNeuroDatasets/{dataset}/master/dataset_description.json",
        }
        if dataset == "ds000117":
            urls["README"] = (
                "https://raw.githubusercontent.com/OpenNeuroDatasets/ds000117/master/README"
            )
        for name, url in urls.items():
            with urllib.request.urlopen(url, timeout=60) as response:
                (directory / name).write_bytes(response.read())
        tree = json.loads((directory / "tree.json").read_text())
        paths = [e["path"] for e in tree["tree"]]
        subjects = sorted(
            {
                p.split("/")[0]
                for p in paths
                if p.startswith("sub-") and p.split("/")[0] != "sub-emptyroom"
            }
        )
        sessions = sorted(
            {
                part
                for p in paths
                if p.startswith("sub-01/")
                for part in p.split("/")
                if part.startswith("ses-")
            }
        )
        metadata = json.loads((directory / "dataset_description.json").read_text())
        summary[dataset] = {
            "git_tree_sha": tree["sha"],
            "truncated": tree.get("truncated", False),
            "dataset_DOI": metadata.get("DatasetDOI"),
            "subjects": len(subjects),
            "selected_subject": "01",
            "selected_sessions": sessions,
            "selected_BOLD_files": sum(p.startswith("sub-01/") and "_bold.nii" in p for p in paths),
            "selected_MEG_files": sum(p.startswith("sub-01/") and "_meg.fif" in p for p in paths),
            "selected_standalone_EEG_files": sum(
                p.startswith("sub-01/") and "_eeg." in p for p in paths
            ),
            "preprocessed_BOLD_files": sum("desc-preproc_bold.nii" in p for p in paths),
            "confounds_tables": sum("desc-confounds_timeseries.tsv" in p for p in paths),
            "modality_note": "EEG may be embedded in MEG FIF; not inspected as a recording",
            "data_downloaded": False,
            "real_analysis_ready": False,
            "metadata_hashes": {p.name: sha256(p) for p in directory.iterdir()},
        }
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
