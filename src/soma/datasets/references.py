"""Official reference discovery, bounded selected downloads and format conversion."""

import gzip
import io
import json
import os
import re
import shutil
import struct
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np

from soma.core.provenance import sha256
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume
from soma.simulations.calibration import atomic_json

BRAINWEB = "https://brainweb.bic.mni.mcgill.ca"
ZENODO = "https://zenodo.org/api/records/22070005"
ROOT = Path("data/raw/references")
DKT31 = [1002, 1003, *range(1005, 1032), 1034, 1035]


def request_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


class RemoteZip(io.RawIOBase):
    """Seekable bounded HTTP-range reader; refuses an ignored Range response."""

    def __init__(self, url: str, size: int, *, offset: int = 0, budget: int = 2 * 1024**3) -> None:
        self.url, self.size, self.offset, self.position, self.budget = url, size, offset, 0, budget
        self.transferred = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        position = (
            offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        )
        if not 0 <= position <= self.size:
            raise ValueError("ZIP seek outside declared object")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        count = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if count == 0:
            return b""
        if self.transferred + count > self.budget:
            raise ValueError("Explicit transfer budget exceeded")
        first = self.offset + self.position
        req = urllib.request.Request(
            self.url, headers={"Range": f"bytes={first}-{first + count - 1}"}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            expected = f"bytes {first}-{first + count - 1}/"
            if response.status != 206 or not response.headers.get("Content-Range", "").startswith(
                expected
            ):
                raise ValueError("Server did not honor exact byte range")
            data = response.read(count + 1)
        if len(data) != count:
            raise ValueError("Truncated/overlong range")
        self.position += count
        self.transferred += count
        return bytes(data)


def discover(root: Path = ROOT, *, fetch: bool = False) -> dict[str, Any]:
    path = root / "discovery.json"
    if path.exists() and not fetch:
        return dict(json.loads(path.read_text()))
    if not fetch:
        raise FileNotFoundError("Explicit references discover/fetch required")
    root.mkdir(parents=True, exist_ok=True)
    zenodo = request_json(ZENODO)
    sources = {}
    for name, url in {
        "brainweb_anatomy": BRAINWEB + "/brainweb/anatomic_normal.html",
        "brainweb_simulation": BRAINWEB + "/brainweb/selection_normal.html",
        "brainweb_formats": BRAINWEB + "/brainweb/about_data_formats.html",
        "mindboggle_license": "https://zenodo.org/records/22070005/files/LICENSE?download=1",
        "mindboggle_author": "https://mindboggle.info/data.html",
    }.items():
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        target = root / (name + ".txt")
        target.write_bytes(data)
        sources[name] = {"url": url, "sha256": sha256(target)}
    result = {
        "brainweb": {
            "model": "original normal",
            "modality": ["T1", "T2", "PD"],
            "slice_mm": [1, 3, 5, 7, 9],
            "noise_percent": [0, 1, 3, 5, 7, 9],
            "RF_percent": [0, 20, 40],
            "shape_XYZ": [181, 217, 181],
            "start_XYZ_mm": [-90, -126, -72],
            "spacing_XYZ_mm": [1, 1, 1],
            "representations": [
                "discrete dominant-tissue integer labels",
                "per-tissue fuzzy membership",
            ],
            "license": (
                "Official citation request; no explicit standard SPDX license "
                "located; no raw redistribution"
            ),
        },
        "mindboggle": {
            "version": "release3 2019-04-03",
            "record": 22070005,
            "DOI": "10.5281/zenodo.22070005",
            "license": "CC BY 4.0; excludes separately licensed subcortical/raw source archives",
            "reference": "manual DKT cortical parcellation, not tissue truth",
            "files": zenodo["files"],
            "selected_subject": "NKI-RS-22-11",
        },
        "source_documents": sources,
    }
    atomic_json(path, result)
    return result


def _publish_stream(source: Any, target: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt = Path(str(target) + ".json")
    if target.exists():
        if not receipt.exists() or json.loads(receipt.read_text())["sha256"] != sha256(target):
            raise ValueError("Reference cache checksum/publication mismatch")
        return dict(json.loads(receipt.read_text()))
    temporary = Path(str(target) + ".partial")
    with temporary.open("wb") as output:
        shutil.copyfileobj(source, output, 16 * 1024**2)
    os.replace(temporary, target)
    value = {
        **provenance,
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": sha256(target),
    }
    atomic_json(receipt, value)
    return value


def validate_minc_gzip(data: bytes) -> None:
    if len(data) > 64 * 1024**2 or data[:2] != b"\x1f\x8b":
        raise ValueError("Expected bounded official gzipped MINC, not HTML")
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        magic = stream.read(8)
    if not (magic.startswith(b"CDF") or magic == b"\x89HDF\r\n\x1a\n"):
        raise ValueError("Empty or non-MINC gzip response")


def fetch_brainweb(root: Path = ROOT) -> dict[str, Any]:
    discover(root, fetch=not (root / "discovery.json").exists())
    results = {}
    for role, alias in [
        ("T1", "t1_icbm_normal_1mm_pn0_rf0"),
        ("labels", "phantom_1.0mm_normal_crisp"),
    ]:
        target = root / "brainweb" / (alias + ".mnc.gz")
        if target.exists():
            validate_minc_gzip(target.read_bytes())
            results[role] = _publish_stream(io.BytesIO(), target, {})
            continue
        resolved_alias = alias
        selection_sha = None
        if role == "T1":
            selection = {
                "from_select": "1",
                "modality_value": "T1",
                "slice_value": "1mm",
                "noise_value": "pn0",
                "field_value": "rf0",
                "download": "[Download]",
            }
            req = urllib.request.Request(
                BRAINWEB + "/cgi/brainweb1", data=urllib.parse.urlencode(selection).encode()
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                html = response.read()
            match = re.search(rb'NAME="do_download_alias" VALUE="([^"]+)"', html)
            if match is None:
                raise ValueError("Official T1 selection did not resolve an alias")
            resolved_alias = match[1].decode()
            selection_path = root / "brainweb" / "selection.html"
            selection_path.parent.mkdir(parents=True, exist_ok=True)
            selection_path.write_bytes(html)
            selection_sha = sha256(selection_path)
        fields = {
            "do_download_alias": resolved_alias,
            "format_value": "minc",
            "zip_value": "gnuzip",
            "who_name": "",
            "who_institution": "",
            "who_email": "",
            "download_for_real": "[Start download!]",
        }
        request = urllib.request.Request(
            BRAINWEB + "/cgi/brainweb1", data=urllib.parse.urlencode(fields).encode()
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(64 * 1024**2 + 1)
        validate_minc_gzip(data)
        results[role] = _publish_stream(
            io.BytesIO(data),
            target,
            {
                "alias": alias,
                "resolved_alias": resolved_alias,
                "selection_document_sha256": selection_sha,
                "source": BRAINWEB,
                "format": "MINC gzip",
                "fields": fields,
            },
        )
    return {
        "dataset": "brainweb",
        "selection": "normal 1mm T1 noise0 RF0 + discrete phantom",
        "assets": results,
    }


def _zip(meta: dict[str, Any], name: str) -> zipfile.ZipFile:
    item = next(x for x in meta["mindboggle"]["files"] if x["key"] == name)
    return zipfile.ZipFile(RemoteZip(item["links"]["self"], item["size"]))


def fetch_mindboggle(root: Path = ROOT, subject: str = "NKI-RS-22-11") -> dict[str, Any]:
    if subject != "NKI-RS-22-11":
        raise ValueError("Only explicitly frozen selected subject supported")
    meta = discover(root, fetch=not (root / "discovery.json").exists())
    target_root = root / "mindboggle"
    target_root.mkdir(parents=True, exist_ok=True)
    assets = {}
    with _zip(meta, "DKT_classifier_evaluation.zip") as archive:
        names = [
            "mindboggle101_atlases_testset.txt",
            "mindboggle101_atlases_trainset.txt",
            "JTAtlas40_Scans.txt",
            f"DKTclassifier_results/{subject}.JTatlas40+aseg.nii.gz",
        ]
        for name in names:
            with archive.open(name) as stream:
                assets[name] = _publish_stream(
                    stream,
                    target_root / Path(name).name,
                    {
                        "archive": "DKT_classifier_evaluation.zip",
                        "entry": name,
                        "role": "external classifier/lineage metadata",
                    },
                )
    with _zip(meta, "Mindboggle101_release3.zip") as archive:
        entry = "Mindboggle101_release3/Mindboggle101_volumes/NKI-RS-22_volumes.tar.gz"
        container = target_root / "NKI-RS-22_volumes.tar.gz"
        with archive.open(entry) as stream:
            transport = _publish_stream(
                stream,
                container,
                {
                    "archive": "Mindboggle101_release3.zip",
                    "entry": entry,
                    "purpose": "cohort compressed transport only; extract one subject",
                },
            )
        inventory = []
        with tarfile.open(container, "r:gz") as tar:
            for member in tar:
                if not member.isfile() or subject not in member.name:
                    continue
                parts = Path(member.name).parts
                if ".." in parts or member.name.startswith("/"):
                    raise ValueError("Unsafe reference archive path")
                inventory.append({"name": member.name, "size": member.size})
                # Keep exact native image/manual labels, preserve member path provenance.
                if member.name.endswith((".nii", ".nii.gz", ".affine.txt")):
                    member_stream = tar.extractfile(member)
                    if member_stream is not None:
                        with member_stream:
                            assets[member.name] = _publish_stream(
                                member_stream,
                                target_root / "selected" / member.name,
                                {
                                    "role": "manual labels/image/transform; exact entry recorded",
                                    "entry": member.name,
                                    "container_sha256": transport["sha256"],
                                },
                            )
    # Cortical surfaces use a stored nested ZIP; range-seek within that member.
    with _zip(meta, "Mindboggle101_release3.zip") as outer:
        name = "Mindboggle101_release3/Mindboggle101_surfaces/NKI-RS-22_surfaces.zip"
        info = outer.getinfo(name)
        if info.compress_type != zipfile.ZIP_STORED:
            raise ValueError("Nested surface ZIP requires stored outer member")
        remote = outer.fp
        assert isinstance(remote, RemoteZip)
        remote.seek(info.header_offset)
        header = remote.read(30)
        fields = struct.unpack("<4s5H3L2H", header)
        offset = info.header_offset + 30 + fields[-2] + fields[-1]
        with zipfile.ZipFile(RemoteZip(remote.url, info.file_size, offset=offset)) as inner:
            surface_inventory = [
                x.filename
                for x in inner.infolist()
                if subject in x.filename and x.filename.endswith(".vtk")
            ]
            for name in surface_inventory:
                with inner.open(name) as stream:
                    assets[name] = _publish_stream(
                        stream,
                        target_root / "surfaces" / name,
                        {
                            "role": "manual cortical surface",
                            "entry": name,
                            "archive": "nested NKI-RS-22_surfaces.zip",
                        },
                    )
    with _zip(meta, "docs.zip") as archive:
        for name in archive.namelist():
            if Path(name).name in (
                "label_definitions.txt",
                "subject_sources_Mindboggle101.txt",
                "subject_list_Mindboggle101.txt",
            ):
                with archive.open(name) as stream:
                    assets[name] = _publish_stream(
                        stream,
                        target_root / Path(name).name,
                        {"role": "official ontology/source attribution", "entry": name},
                    )
    value = {
        "dataset": "mindboggle-101",
        "subject": subject,
        "license": "CC BY 4.0",
        "transport": transport,
        "retained_assets": assets,
        "subject_inventory": inventory,
        "surface_inventory": surface_inventory,
        "whole_dataset_downloaded": False,
    }
    atomic_json(target_root / "selection.json", value)
    return value


def load_reference(
    path: Path, *, kind: str, subject: str, space: str, units_override: str | None = None
) -> Volume:
    if not subject or not space or kind not in ("labels", "intensity"):
        raise ValueError("Explicit identity, space and role required")
    if ".mnc" in path.name:
        image: Any = nib.load(path)
        array = np.asanyarray(image.dataobj)
        affine = np.asarray(image.affine, dtype=float)
        affine[:3] *= 0.001
        metadata = {
            "source_format": "MINC",
            "original_affine_mm": image.affine.tolist(),
            "source_sha256": sha256(path),
            "axis_policy": (
                "nibabel MINC actual header axis/direction/start/step, not an invented NIfTI grid"
            ),
        }
        if kind == "labels":
            if not np.isfinite(array).all() or not np.allclose(
                array, np.rint(array), atol=1e-5, rtol=0
            ):
                raise ValueError("Discrete reference must be exact integer labels")
            array = np.rint(array).astype(np.int16)
        volume = Volume(array, affine, "labels" if kind == "labels" else "intensity", metadata)
    else:
        volume = load_nifti(
            path,
            kind="labels" if kind == "labels" else "intensity",
            policy="nibabel",
            units_override=units_override,
        )
    if kind == "labels" and volume.dtype.kind not in "biu":
        data = volume.array()
        if (
            not np.isfinite(data).all()
            or np.any(data < 0)
            or not np.allclose(data, np.rint(data), atol=1e-5, rtol=0)
        ):
            raise ValueError("Stored float labels must be exact nonnegative integer codes")
        volume = Volume(
            np.rint(data).astype(np.int32),
            volume.affine_m,
            "labels",
            {
                **volume.metadata,
                "integer_cast": "exact integral stored float codes; no intensity segmentation",
            },
        )
    return Volume(
        volume.data,
        volume.affine_m,
        volume.kind,
        {**volume.metadata, "subject": subject, "space": space, "path": str(path)},
    )


def read_cortical_surface(path: Path, subject: str) -> dict[str, Any]:
    """Read supplied ASCII triangular VTK without inventing a volume-frame chain."""
    if subject not in path.parts:
        raise ValueError("Cortical surface subject/path mismatch")
    text = path.read_text()
    if "ASCII" not in text.splitlines()[:4] or "DATASET POLYDATA" not in text:
        raise ValueError("Only supplied ASCII VTK POLYDATA is supported")
    point = re.search(r"POINTS\s+(\d+)\s+\w+\s*\n", text)
    polygon = re.search(r"POLYGONS\s+(\d+)\s+(\d+)\s*\n", text)
    if point is None or polygon is None:
        raise ValueError("Missing VTK geometry")
    n = int(point[1])
    m = int(polygon[1])
    points = np.fromstring(text[point.end() : polygon.start()], sep=" ", count=n * 3).reshape(n, 3)
    faces = np.fromstring(text[polygon.end() :], sep=" ", count=int(polygon[2]), dtype=int).reshape(
        m, 4
    )
    if (
        np.any(faces[:, 0] != 3)
        or not np.isfinite(points).all()
        or faces[:, 1:].min() < 0
        or faces[:, 1:].max() >= n
    ):
        raise ValueError("Invalid nontriangular VTK surface")
    scalar = re.search(r"SCALARS[^\n]*\nLOOKUP_TABLE[^\n]*\n", text)
    labels = (
        np.fromstring(text[scalar.end() :], sep=" ", count=n, dtype=int)
        if scalar
        else np.empty(0, dtype=int)
    )
    return {
        "points_as_stored_mm": points,
        "faces": faces[:, 1:],
        "manual_labels": labels,
        "subject": subject,
        "sha256": sha256(path),
        "coordinate_frame": "not independently established; no surface-to-volume chain assumed",
    }
