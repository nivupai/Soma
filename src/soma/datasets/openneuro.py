"""OpenNeuro ds000117 metadata and explicitly selected-subject retrieval only."""

import json
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

from soma.core.provenance import sha256
from soma.simulations.calibration import atomic_json

BASE = "https://s3.amazonaws.com/openneuro.org/ds000117/"
REPOSITORY = "https://api.github.com/repos/OpenNeuroDatasets/ds000117"


def discover_ds000117(
    cache: Path = Path("data/raw/ds000117/metadata"), *, refresh: bool = False
) -> dict[str, Any]:
    receipt = cache / "discovery.json"
    if receipt.exists() and not refresh:
        return dict(json.loads(receipt.read_text()))
    cache.mkdir(parents=True, exist_ok=True)

    def request(url: str) -> Any:
        with urllib.request.urlopen(
            urllib.request.Request(
                url, headers={"User-Agent": "Soma anatomical metadata research"}
            ),
            timeout=60,
        ) as response:
            return json.load(response)

    repo = request(REPOSITORY)
    branch = repo["default_branch"]
    tree = request(f"{REPOSITORY}/git/trees/{branch}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Metadata inventory truncated; selected-subject discovery is incomplete")
    with urllib.request.urlopen(
        f"https://raw.githubusercontent.com/OpenNeuroDatasets/ds000117/{branch}/dataset_description.json",
        timeout=60,
    ) as response:
        description = json.load(response)
    paths = [x["path"] for x in tree["tree"] if x["type"] == "blob"]
    subjects = sorted({p.split("/")[0] for p in paths if p.startswith("sub-")})
    result = {
        "dataset": "ds000117",
        "description": description,
        "license": description.get("License", "UNSPECIFIED"),
        "license_scope": "current BIDS snapshot, not historical OpenfMRI release",
        "repository_tree_sha": tree["sha"],
        "metadata_source": REPOSITORY,
        "subjects": [s for s in subjects if s != "sub-emptyroom"],
        "nonparticipant_recordings": [s for s in subjects if s == "sub-emptyroom"],
        "files": paths,
        "downloaded_data_files": False,
        "individual_model_ready": False,
        "missing_for_individual_forward": (
            "subject-specific reconstructed boundaries/source space and "
            "justified sensor↔MRI transform must be supplied and "
            "validated"
        ),
    }
    atomic_json(receipt, result)
    return result


def selected_inventory(metadata: dict[str, Any], subject: str) -> dict[str, Any]:
    if subject == "sub-emptyroom" or subject not in metadata["subjects"]:
        raise ValueError("Requested participant not in ds000117 metadata")
    files = [p for p in metadata["files"] if p.startswith(subject + "/")]
    return {
        "dataset": "ds000117",
        "subject": subject,
        "license": metadata["license"],
        "metadata_tree_sha": metadata["repository_tree_sha"],
        "files": files,
        "automatic_download": False,
        "identity_evidence": (
            "BIDS subject path correspondence; modality/coregistration remains to be validated"
        ),
    }


def fetch_selected(
    subject: str,
    files: list[str],
    root: Path = Path("data/raw/ds000117"),
    *,
    maximum_bytes: int = 1024**3,
) -> dict[str, Any]:
    if not files or not subject.startswith("sub-") or "/" in subject or maximum_bytes <= 0:
        raise ValueError("Explicit participant and nonempty selected file list required")
    inventory = selected_inventory(discover_ds000117(root / "metadata"), subject)
    total = 0
    outputs = {}
    for name in files:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or name not in inventory["files"]
            or not name.startswith(subject + "/")
        ):
            raise ValueError("Selected file escapes or mismatches the requested subject")
        url = BASE + name
        with urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"), timeout=60
        ) as response:
            size = int(response.headers["Content-Length"])
        total += size
        if total > maximum_bytes:
            raise ValueError("Explicit selected-subject download exceeds byte budget")
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(destination.name + ".partial")
            with (
                urllib.request.urlopen(url, timeout=60) as response,
                temporary.open("wb") as stream,
            ):
                written = 0
                while block := response.read(1024 * 1024):
                    written += len(block)
                    if written > size:
                        raise ValueError("Selected file response exceeded declared size")
                    stream.write(block)
            if temporary.stat().st_size != size:
                raise OSError("Truncated selected-subject data file")
            temporary.replace(destination)
        outputs[name] = {
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "url": url,
        }
    result = {
        **inventory,
        "selected_files": outputs,
        "total_selected_bytes": total,
        "individual_forward_ready": False,
    }
    atomic_json(root / f"{subject}-selection.json", result)
    return result
