"""Explicit bounded acquisition of the pinned official SCI reference archives.

Run manually with network permission. Never registered-data access or full FEM
acquisition. The selected archive bytes are pinned in external-discovery.json.
"""

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path


def main() -> None:
    receipt = json.loads(Path(__file__).with_name("external-discovery.json").read_text())
    root = Path("data/raw/references/sci-head")
    root.mkdir(parents=True, exist_ok=True)
    selections = {
        "T1.zip": ["T1/T1_Corrected.nrrd", "T1/README.txt"],
        "Segmentation.zip": ["Segmentation/HeadSegmentation.nrrd", "Segmentation/README.txt"],
        "AcquisitionReports.zip": ["Acquitisition Reports/README.txt"],
        "Simulations.zip": [
            "Simulations/README.txt",
            "Simulations/forward_problem.srn",
            "Simulations/LeadFieldMatrix.srn",
            "Simulations/LeadFieldMatrix_anisotropic.srn",
        ],
    }
    for name, meta in receipt["archives"].items():
        target = root / name
        if not target.exists():
            partial = target.with_suffix(target.suffix + ".partial")
            digest = hashlib.sha256()
            count = 0
            with (
                urllib.request.urlopen(meta["url"], timeout=60) as response,
                partial.open("xb") as stream,
            ):
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    count += len(block)
                    if count > meta["bytes"]:
                        raise ValueError("Official archive exceeds pinned size")
                    digest.update(block)
                    stream.write(block)
            if count != meta["bytes"] or digest.hexdigest() != meta["sha256"]:
                raise ValueError(
                    "Official archive differs from pinned reference; partial preserved"
                )
            partial.rename(target)
        if (
            target.stat().st_size != meta["bytes"]
            or hashlib.sha256(target.read_bytes()).hexdigest() != meta["sha256"]
        ):
            raise ValueError("Existing SCI archive differs from recorded reference")
        with zipfile.ZipFile(target) as archive:
            for member in selections[name]:
                info = archive.getinfo(member)
                if info.file_size > 128 * 1024**2:
                    raise ValueError("Selected member exceeds bound")
                destination = root / member
                if destination.exists():
                    expected = receipt["selected_assets"][member]["sha256"]
                    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                        raise ValueError("Existing selected SCI asset differs")
                    continue
                payload = archive.read(member)
                if (
                    hashlib.sha256(payload).hexdigest()
                    != receipt["selected_assets"][member]["sha256"]
                ):
                    raise ValueError("Selected SCI member checksum differs")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as stream:
                    stream.write(payload)
    print("Pinned SCI archives and selected assets verified; no FEM or registered dataset fetched.")


if __name__ == "__main__":
    main()
