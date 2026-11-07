"""Explicit anatomy-only retrieval from the official SPM auditory BIDS archive."""

import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.simulations.calibration import atomic_json

SPM_URL = "https://www.fil.ion.ucl.ac.uk/spm/download/data/MoAEpilot/MoAEpilot.bids.zip"
TERMS_URL = "https://www.fil.ion.ucl.ac.uk/spm/data/auditory/"
TERMS = (
    "Personal education and evaluation; other uses require contacting FIL methods group. "
    "Not the SPM software license."
)


class _RemoteZip(io.RawIOBase):
    def __init__(self, url: str) -> None:
        self.url, self.position = url, 0
        self.ranges: list[list[int]] = []
        with urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"), timeout=60
        ) as response:
            self.length = int(response.headers["Content-Length"])
            self.etag = response.headers.get("ETag")
        if self.length <= 0:
            raise ValueError("Archive length is unavailable")

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        self.position = (
            offset
            if whence == 0
            else self.position + offset
            if whence == 1
            else self.length + offset
        )
        if not 0 <= self.position <= self.length:
            raise ValueError("Invalid remote ZIP seek")
        return self.position

    def read(self, size: int = -1) -> bytes:
        size = min(self.length - self.position, self.length if size < 0 else size)
        if size == 0:
            return b""
        first, last = self.position, self.position + size - 1
        headers = {"Range": f"bytes={first}-{last}"}
        if self.etag:
            headers["If-Match"] = self.etag
        with urllib.request.urlopen(
            urllib.request.Request(self.url, headers=headers), timeout=60
        ) as response:
            if (
                response.status != 206
                or response.headers.get("Content-Range") != f"bytes {first}-{last}/{self.length}"
            ):
                raise RuntimeError(
                    "Server lacks exact range support; refusing full functional archive download"
                )
            data = response.read(size + 1)
        if len(data) != size:
            raise OSError("Truncated or oversized archive byte range")
        self.position += size
        self.ranges.append([first, last])
        return bytes(data)


def fetch_structural(root: Path) -> tuple[Path, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    path, receipt = root / "spm-auditory-T1w.nii", root / "spm-auditory.json"
    if path.exists():
        metadata = json.loads(receipt.read_text())
        if metadata["sha256"] != sha256(path):
            raise ValueError("Structural dataset checksum mismatch")
        return path, metadata
    remote = _RemoteZip(SPM_URL)
    with zipfile.ZipFile(remote) as archive:
        names = archive.namelist()
        candidates = [n for n in names if "/anat/" in n and n.endswith(("_T1w.nii.gz", "_T1w.nii"))]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one structural T1w member, found {candidates}; archive names {names}"
            )
        member = candidates[0]
        data = archive.read(member)  # ZIP verifies the member CRC; no functional member is read.
    temporary = path.with_suffix(".partial")
    temporary.write_bytes(data)
    temporary.replace(path)
    metadata = {
        "dataset": "spm-auditory",
        "subject": "SPM-auditory-01",
        "modality": "T1w structural",
        "source_url": SPM_URL,
        "terms_url": TERMS_URL,
        "terms": TERMS,
        "archive_member": member,
        "archive_etag": remote.etag,
        "archive_size_bytes": remote.length,
        "http_byte_ranges": remote.ranges,
        "downloaded_bytes": sum(b - a + 1 for a, b in remote.ranges),
        "functional_files_downloaded": False,
        "sha256": sha256(path),
    }
    atomic_json(receipt, metadata)
    return path, metadata


def cached_structural(root: Path) -> tuple[Path, dict[str, Any]]:
    path, receipt = root / "spm-auditory-T1w.nii", root / "spm-auditory.json"
    if not path.exists() or not receipt.exists():
        raise FileNotFoundError("Structural anatomy is not cached; explicitly use --fetch")
    metadata = json.loads(receipt.read_text())
    if metadata["sha256"] != sha256(path):
        raise ValueError("Structural dataset checksum mismatch")
    return path, metadata
