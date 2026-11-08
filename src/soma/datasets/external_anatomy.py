"""Offline-first SCI computational model and authorized local tissue references."""

import gzip
import math
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np

from soma.core.provenance import sha256
from soma.imaging.volumes import Volume

SCI_SOURCE = "https://sci.utah.edu/sci-head-model/"
TISSUES = {1: "CSF", 2: "gray matter", 3: "white matter"}


def read_nrrd(path: Path) -> tuple[Any, dict[str, str]]:
    """Bounded scalar 3D NRRD ingestion; never guess a coordinate frame or units."""
    with path.open("rb") as stream:
        if not stream.readline().startswith(b"NRRD000"):
            raise ValueError("Not a NRRD file")
        lines = []
        for _ in range(200):
            line = stream.readline()
            if not line.strip():
                break
            lines.append(line.decode("ascii").strip())
        else:
            raise ValueError("Unbounded NRRD header")
        h = dict(x.split(": ", 1) for x in lines if ": " in x and not x.startswith("#"))
        sizes = tuple(int(x) for x in h.get("sizes", "").split())
        if h.get("dimension") != "3" or len(sizes) != 3 or min(sizes) <= 0:
            raise ValueError("Explicit scalar 3D NRRD required")
        types = {
            "unsigned char": "u1",
            "uchar": "u1",
            "float": "<f4",
            "double": "<f8",
            "short": "<i2",
            "unsigned short": "<u2",
        }
        if (
            h.get("type") not in types
            or h.get("encoding") not in ("gzip", "raw")
            or "data file" in h
        ):
            raise ValueError("Unsupported NRRD payload; detached/implicit formats refused")
        dtype = np.dtype(types[h["type"]])
        if dtype.itemsize > 1 and h.get("endian") != "little":
            raise ValueError("Explicit little-endian NRRD required")
        count = math.prod(sizes) * dtype.itemsize
        if count > 512 * 1024**2:
            raise ValueError("NRRD exceeds bounded ingestion budget")
        reader = gzip.GzipFile(fileobj=stream) if h["encoding"] == "gzip" else stream
        data = reader.read(count + 1)
        if len(data) != count:
            raise ValueError("NRRD payload does not match declared dimensions")
    values = np.frombuffer(data, dtype=dtype).reshape(sizes, order="F")
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite NRRD data")
    return values, h


def nrrd_volume(
    path: Path,
    *,
    kind: Literal["intensity", "labels"] = "intensity",
    units_override: str | None = None,
    space_override: str | None = None,
    justification: str | None = None,
) -> Volume:
    data, h = read_nrrd(path)
    space = h.get("space")
    if units_override or space_override:
        if not justification:
            raise ValueError("Coordinate/units overrides need documented external evidence")
    space = space_override or space
    if space not in ("left-posterior-superior", "right-anterior-superior"):
        raise ValueError("NRRD anatomical frame unestablished; 3D-right-handed is insufficient")
    unit = units_override or h.get("space units", "").replace('"', "").strip()
    if unit not in ("mm", "mm mm mm", "m", "m m m"):
        raise ValueError("NRRD physical units require evidence")
    directions = np.array(
        [
            [float(v) for v in x.split(",")]
            for x in re.findall(r"\(([^)]+)\)", h["space directions"])
        ]
    ).T
    origin = np.array([float(v) for v in h["space origin"].strip("()").split(",")])
    affine = np.eye(4)
    affine[:3, :3], affine[:3, 3] = directions, origin
    affine[:3] *= 0.001 if unit.startswith("mm") else 1.0
    if space == "left-posterior-superior":
        affine = np.diag([-1.0, -1.0, 1.0, 1.0]) @ affine
    if kind not in ("intensity", "labels"):
        raise ValueError("Unknown volume kind")
    return Volume(
        data,
        affine,
        kind,
        {
            "path": str(path),
            "sha256": sha256(path),
            "NRRD": h,
            "units_override": units_override,
            "space_override": space_override,
            "justification": justification,
        },
    )


def inspect_sci(root: Path = Path("data/raw/references/sci-head")) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset": "sci-head",
        "subject": "SCI single female participant (no public subject code)",
        "institution": "University of Utah SCI; acquisition EGI/University of Oregon",
        "version": "Warner et al. 2019, DOI 10.1101/552190; archive last-modified 2019-02-19",
        "source": SCI_SOURCE,
        "evidence_type": (
            "external computational segmentation, Seg3D; "
            "annotation process not specified by archive README"
        ),
        "usage": (
            "public, attribution requested; NIH P41 GM103545 and "
            "R24 GM136986 acknowledgments; no inferred SPDX license"
        ),
        "mesh": {
            "representation": "Cleaver eight-tissue tetrahedral FEM",
            "downloaded": False,
            "BEM_interchangeable": False,
            "coordinate_chain": "not established",
        },
        "conductivity": {
            "network_index_S_m": [0.0, 1.79, 0.5051, 0.3333, 1e-6, 0.4336, 0.01, 0.1429],
            "source": "official Simulations/LeadFieldMatrix.srn CreateMatrix data",
            "label_names_verified": False,
            "warning": (
                "network and paper values differ; network indices 0..7 "
                "versus stored labels 1..8; no automatic BEM assignment"
            ),
        },
        "assets": {},
        "missing": [],
        "BEM_readiness": "INDETERMINATE",
        "blocked_checks": [
            "segmentation anatomical frame and units",
            "verified ID-to-tissue ontology",
            "three-layer conductor interface correspondence",
            "sensor/source transform chain",
            "independent anatomical boundary evidence",
        ],
    }
    for name, relative in [
        ("T1", "T1/T1_Corrected.nrrd"),
        ("segmentation", "Segmentation/HeadSegmentation.nrrd"),
    ]:
        p = root / relative
        if not p.exists():
            result["missing"].append(str(p))
            continue
        data, header = read_nrrd(p)
        asset: dict[str, Any] = {
            "path": str(p),
            "sha256": sha256(p),
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "header": header,
            "finite": True,
            "range": [float(data.min()), float(data.max())],
        }
        if name == "segmentation":
            codes, counts = np.unique(data, return_counts=True)
            asset["label_counts"] = {
                str(int(k)): int(v) for k, v in zip(codes, counts, strict=True)
            }
        result["assets"][name] = asset
    result["archives"] = {
        p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in root.glob("*.zip")
    }
    result["status"] = (
        "available_with_unresolved_geometry" if len(result["assets"]) == 2 else "missing_assets"
    )
    return result


def local_reference_manifest(path: Path) -> dict[str, Any]:
    """No network or hidden-label discovery; authorized paths are caller supplied."""
    import json

    if not path.exists():
        return {
            "status": "unavailable",
            "subjects": [],
            "diagnostic": (
                "No authorized local manifest; MRBrainS13 "
                "registration/IBSR NITRC login required. No bypass attempted."
            ),
        }
    value = json.loads(path.read_text())
    if not value.get("authorization") or value.get("dataset") not in (
        "mrbrains13",
        "ibsr-v2",
        "external-authorized",
    ):
        raise ValueError("Explicit authorized dataset and provenance manifest required")
    if not isinstance(value.get("subjects"), list):
        raise ValueError("Subject records required")
    return dict(value)


def ingest_mrbrains13_training(
    image_path: Path,
    label_path: Path,
    *,
    subject: str,
    split: str,
    authorization: str,
    native_label_names: dict[int, str],
) -> tuple[Volume, Volume, Any, dict[str, Any]]:
    """Authorized training labels only; return explicit CB/brainstem exclusion mask.

    Cerebellum/brainstem cannot be scored as background or relabeled into tissues.
    The exclusion mask must accompany any downstream evaluation; this is an
    ingestion adapter, not a hidden-test challenge submission/evaluation client.
    """
    from soma.datasets.references import load_reference

    names = {
        0: "background",
        1: "cortical gray matter",
        2: "basal ganglia",
        3: "white matter",
        4: "white matter lesions",
        5: "peripheral CSF",
        6: "lateral ventricles",
        7: "cerebellum",
        8: "brainstem",
    }
    if (
        not authorization
        or not subject
        or split not in ("development", "holdout")
        or native_label_names != names
        or "LabelsForTraining" not in label_path.name
    ):
        raise ValueError("Authorized documented MRBrainS13 training labels and split required")
    image = load_reference(image_path, kind="intensity", subject=subject, space="MRBrainS13-native")
    native = load_reference(label_path, kind="labels", subject=subject, space="MRBrainS13-native")
    if not image.same_grid(native):
        raise ValueError("MRBrainS13 training MRI/label geometry mismatch")
    values = native.array()
    if not set(np.unique(values)).issubset(names):
        raise ValueError("Unknown MRBrainS13 training label")
    mapping = {0: 0, 1: 2, 2: 2, 3: 3, 4: 3, 5: 1, 6: 1, 7: 0, 8: 0}
    canonical = np.zeros(native.shape, dtype=np.uint8)
    for source, target in mapping.items():
        canonical[values == source] = target
    excluded = np.isin(values, [7, 8])
    provenance = {
        "dataset": "mrbrains13",
        "subject": subject,
        "split": split,
        "access": "authorized local training data, no hidden labels",
        "evidence_type": "manual training annotations; not error-free truth",
        "native_label_names": names,
        "mapping": mapping,
        "excluded_native_labels": [7, 8],
        "exclusion_required_for_scoring": True,
        "image_sha256": sha256(image_path),
        "label_sha256": sha256(label_path),
        "source": "https://research.chalmers.se/publication/230909/file/230909_Fulltext.pdf",
    }
    return image, Volume(canonical, native.affine_m, "labels", provenance), excluded, provenance
