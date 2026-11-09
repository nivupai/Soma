"""Explicit bounded ds000114 metadata/pilot fetch; never fetch other participants."""

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from soma.core.provenance import sha256, write_json


def retrieve(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    root = Path("data/external/ds000114")
    root.mkdir(parents=True, exist_ok=True)
    evidence = Path("data/derived/milestone14/raw-inspection")
    evidence.mkdir(parents=True, exist_ok=False)
    base = "https://raw.githubusercontent.com/OpenNeuroDatasets/ds000114/master/"
    tree = json.loads(
        retrieve(
            "https://api.github.com/repos/OpenNeuroDatasets/ds000114/git/trees/master?recursive=1"
        )
    )
    if tree.get("truncated"):
        raise ValueError("Incomplete remote inventory")
    write_json(evidence / "tree.json", tree)
    files = [e["path"] for e in tree["tree"]]
    metadata = [
        "dataset_description.json",
        "task-fingerfootlips_bold.json",
        "task-fingerfootlips_events.tsv",
    ]
    for name in metadata:
        (root / name).write_bytes(retrieve(base + name))
    description = json.loads((root / "dataset_description.json").read_text())
    if description.get("DatasetDOI") != "doi:10.18112/openneuro.ds000114.v1.0.2":
        raise ValueError("Dataset version differs from frozen protocol")
    selected = [
        p
        for p in files
        if p.startswith("sub-01/")
        and (p.endswith("_T1w.nii.gz") or p.endswith("_task-fingerfootlips_bold.nii.gz"))
    ]
    if len(selected) != 4:
        raise ValueError("Unexpected selected pilot file coverage")
    receipts = []
    for name in selected:
        pointer = retrieve(base + name).decode()
        match = re.search(r"(SHA256E|MD5E)-s(\d+)--([0-9a-f]+)", pointer)
        if not match:
            raise ValueError("Unsupported/unverified annex pointer")
        algorithm = "sha256" if match[1] == "SHA256E" else "md5"
        row = {
            "path": name,
            "annex_algorithm": algorithm,
            "expected_size": int(match[2]),
            "annex_digest": match[3],
        }
        if args.fetch:
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError("Pilot input exists; do not overwrite")
            temporary = destination.with_name("." + destination.name + ".part")
            digest = hashlib.new(algorithm)
            count = 0
            with (
                urllib.request.urlopen(
                    "https://s3.amazonaws.com/openneuro.org/ds000114/" + name, timeout=60
                ) as response,
                temporary.open("xb") as stream,
            ):
                while block := response.read(1024 * 1024):
                    stream.write(block)
                    digest.update(block)
                    count += len(block)
            if count != int(match[2]) or digest.hexdigest() != match[3]:
                raise ValueError("Downloaded pilot content differs from annex identity")
            temporary.rename(destination)
            row["sha256"] = sha256(destination)
            row["downloaded"] = True
        receipts.append(row)
    write_json(
        evidence / "inventory.json",
        {
            "tree_sha": tree["sha"],
            "description": description,
            "subjects_in_remote_tree": len(
                {p.split("/")[0] for p in files if p.startswith("sub-")}
            ),
            "preprocessed_BOLD_in_tree": sum("desc-preproc_bold.nii" in p for p in files),
            "pilot_assets": receipts,
            "metadata_sha256": {p: sha256(root / p) for p in metadata},
            "all_other_subject_images_fetched": False,
        },
    )
    print("Bounded metadata/pilot retrieval completed; no model outcomes inspected.")


if __name__ == "__main__":
    main()
