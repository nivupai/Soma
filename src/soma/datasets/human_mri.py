"""Inspected local human MRI releases; no downloads and no hidden-test label reads."""

import hashlib
import json
import re
import zipfile
from itertools import product
from pathlib import Path
from typing import Any, Literal

import nibabel as nib
import numpy as np

from soma.core.provenance import sha256
from soma.datasets.external_anatomy import TISSUES
from soma.imaging.nifti import load_nifti
from soma.imaging.resampling import resample
from soma.imaging.segmentation import require_labels
from soma.imaging.volumes import Volume

MR_NAMES = {
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
MR_MAPPING = {0: 0, 1: 2, 2: 2, 3: 3, 4: 3, 5: 1, 6: 1, 7: 0, 8: 0}


def safe_local_output(path: Path) -> None:
    """Participant outputs within this checkout must remain in ignored trees."""
    repo = Path(__file__).resolve().parents[3]
    target = path.resolve()
    if target.is_relative_to(repo):
        allowed = [(repo / "reports").resolve(), (repo / "data/derived").resolve()]
        if not any(target.is_relative_to(p) for p in allowed):
            raise ValueError(
                "Human participant outputs must remain under ignored reports/data/derived"
            )
        import subprocess

        result = subprocess.run(
            ["git", "check-ignore", "--quiet", str(target / "output-sentinel")],
            cwd=repo,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("Human participant output exclusion is not active")


def corner_displacement_mm(a: Any, b: Any, shape: tuple[int, ...]) -> float:
    corners = np.array(list(product(*[(0, n - 1) for n in shape[:3]])))
    x = corners @ np.asarray(a)[:3, :3].T + np.asarray(a)[:3, 3]
    y = corners @ np.asarray(b)[:3, :3].T + np.asarray(b)[:3, 3]
    return float(np.linalg.norm(x - y, axis=1).max())


def nifti_metadata(path: Path) -> dict[str, Any]:
    image: Any = nib.load(path)
    q, qc = image.get_qform(coded=True)
    s, sc = image.get_sform(coded=True)
    affine = np.asarray(image.affine)
    return {
        "path": str(path),
        "sha256": sha256(path),
        "shape": list(image.shape),
        "dtype": str(image.get_data_dtype()),
        "spacing_header": list(map(float, image.header.get_zooms()[:3])),
        "units": list(image.header.get_xyzt_units()),
        "axis_codes": list(nib.aff2axcodes(affine)),
        "qform_code": int(qc),
        "sform_code": int(sc),
        "qform": None if q is None else q.tolist(),
        "sform": None if s is None else s.tolist(),
        "qform_sform_corner_difference_mm": corner_displacement_mm(q, s, image.shape)
        if qc and sc
        else None,
        "header_free_text_exported": False,
    }


def access_metadata(mrbrains_root: Path, ibsr_root: Path | None) -> dict[str, Any]:
    readmes = [p for p in mrbrains_root.iterdir() if p.name.lower() == "readme.txt"]
    manifests = [p for p in mrbrains_root.iterdir() if p.name.lower() == "manifest.txt"]
    if len(readmes) != 1 or len(manifests) != 1:
        raise ValueError("One local MRBrainS Readme and manifest required")
    readme = readmes[0].read_text()
    manifest = manifests[0].read_text()
    required = [
        "T1_1mm.nii",
        "T1_IR.nii",
        "T2_FLAIR.nii",
        "LabelsForTraining.nii",
        "LabelsForTesting.nii",
        "Cortical gray matter",
        "Basal ganglia",
        "Brainstem",
        "cerebellum are excluded",
    ]
    if not all(x in readme for x in required):
        raise ValueError(
            "Local documentation does not establish the supported MRBrainS13 ontology/grid policy"
        )
    declarations = {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"([A-Za-z0-9_.]+)\s+\([^)]*\)\s+(\d+) bytes", manifest)
    }
    if set(declarations) != {"TrainingData.zip", "TestData.zip", "Readme.txt"}:
        raise ValueError("Unsupported MRBrainS distribution manifest")
    checks = {
        name: {
            "declared_bytes": size,
            "actual_bytes": (mrbrains_root / name).stat().st_size
            if (mrbrains_root / name).exists()
            else None,
        }
        for name, size in declarations.items()
    }
    # Text newline conversion is reported; archive size differences reject identity.
    for name in ["TrainingData.zip", "TestData.zip"]:
        if (
            checks[name]["actual_bytes"] is not None
            and checks[name]["actual_bytes"] != checks[name]["declared_bytes"]
        ):
            raise ValueError("Local archive size differs from distribution manifest: " + name)
    ibsr_readmes = (
        []
        if ibsr_root is None
        else [p for p in ibsr_root.rglob("*") if p.name.lower() == "readme.txt"]
    )
    if ibsr_root is not None and (
        not ibsr_readmes or not any("Rohlfing" in p.read_text() for p in ibsr_readmes)
    ):
        raise ValueError("Local IBSR release notice required")
    return {
        "MRBrainS": {
            "identity": "MRBrainS13-compatible documented 5-training/15-test release",
            "readme_sha256": sha256(readmes[0]),
            "manifest_sha256": sha256(manifests[0]),
            "manifest_sizes": checks,
            "labels": "manual eight-class training annotations",
            "permission_basis": "user-authorized local segmentation methods research",
            "license_in_local_documents": False,
            "restrictions": (
                "No redistribution or broader/commercial "
                "permission inferred; portal agreement not supplied"
            ),
            "test_partition_policy": "file-name inventory only; no header/payload/hash reads",
        },
        "IBSR": {
            "identity": "IBSR v2 skull-stripped NIfTI release",
            "local_notice_sha256": [sha256(p) for p in ibsr_readmes],
            "usage": (
                "Local notice states Rohlfing public-domain "
                "release with requested citation; no raw redistribution"
            ),
        },
        "participant_information_policy": (
            "Local ignored records only; no participant metadata or images in Git"
        ),
    }


def discover_human(ibsr_root: Path, mrbrains_root: Path) -> dict[str, Any]:
    access = access_metadata(mrbrains_root, ibsr_root)
    records: list[dict[str, Any]] = []
    failures = []
    seen = set()
    files: list[dict[str, Any]] = []
    roles = ["ana", "ana_strip", "ana_brainmask", "seg_ana", "segTRI_ana", "segTRI_fill_ana"]
    directories = sorted(
        p for p in ibsr_root.rglob("*") if p.is_dir() and re.fullmatch(r"IBSR_\d+", p.name)
    )
    for d in directories:
        sid = "ibsr-v2:" + d.name
        if sid in seen:
            raise ValueError("Ambiguous repeated IBSR subject directory")
        seen.add(sid)
        chosen = {}
        for role in roles:
            candidates = [
                p
                for p in d.iterdir()
                if p.name in (d.name + "_" + role + ".nii", d.name + "_" + role + ".nii.gz")
            ]
            compressed = [p for p in candidates if p.name.endswith(".nii.gz")]
            preferred = compressed or candidates
            if len(preferred) == 1:
                chosen[role] = str(preferred[0])
            elif len(preferred) > 1:
                raise ValueError("Ambiguous same-role MRI files")
        for p in sorted(d.iterdir()):
            if p.name.endswith((".nii", ".nii.gz")):
                files.append({"dataset": "ibsr-v2", "subject": sid, **nifti_metadata(p)})
        if not {"ana_strip", "segTRI_ana"}.issubset(chosen):
            failures.append(
                {"subject": sid, "reason": "Missing stripped image/non-filled tissue reference"}
            )
            continue
        records.append(
            {
                "dataset": "ibsr-v2",
                "subject": sid,
                "partition": "development",
                "image": chosen["ana_strip"],
                "reference": chosen["segTRI_ana"],
                "roles": chosen,
                "space": sid + "-native",
            }
        )
    training = mrbrains_root / "training"
    directories = (
        sorted({p.parent for p in training.rglob("LabelsForTraining.nii")})
        if training.exists()
        else []
    )
    archive = mrbrains_root / "TrainingData.zip"
    archive_members = {}
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                # Names and bytes only for matching TRAINING members; no test archive.
                if not info.is_dir() and info.filename.endswith(".nii"):
                    archive_members[info.filename] = hashlib.sha256(z.read(info)).hexdigest()
    for d in directories:
        if not re.fullmatch(r"\d+", d.name):
            failures.append({"path": str(d), "reason": "Unsupported training subject ID"})
            continue
        sid = "mrbrains13-training:" + d.name
        if sid in seen:
            raise ValueError("Repeated MRBrainS training identity")
        seen.add(sid)
        if not (d / "T1.nii").is_file():
            failures.append({"subject": sid, "reason": "Missing registered T1"})
            continue
        for p in sorted(d.glob("*.nii")):
            meta = nifti_metadata(p)
            matches = [
                h
                for name, h in archive_members.items()
                if name.endswith("/" + d.name + "/" + p.name)
            ]
            meta["training_archive_member_matches"] = (
                len(matches) == 1 and matches[0] == meta["sha256"]
            )
            if archive_members and not meta["training_archive_member_matches"]:
                raise ValueError("Extracted training image does not match declared archive member")
            files.append({"dataset": "mrbrains13", "subject": sid, **meta})
        records.append(
            {
                "dataset": "mrbrains13",
                "subject": sid,
                "partition": "external",
                "image": str(d / "T1.nii"),
                "reference": str(d / "LabelsForTraining.nii"),
                "testing_style_reference": str(d / "LabelsForTesting.nii"),
                "space": sid + "-native",
            }
        )
    if len(records) != len({r["subject"] for r in records}):
        raise ValueError("Subject identity collision")
    inputs = [r["image"] for r in records]
    if len(set(sha256(Path(p)) for p in inputs)) != len(inputs):
        raise ValueError("Repeated MRI content across development/external identities")
    return {
        "access": access,
        "subjects": records,
        "files": files,
        "failures": failures,
        "test_inventory": [
            str(p.relative_to(mrbrains_root))
            for p in sorted((mrbrains_root / "test").rglob("*"))
            if p.is_file()
        ],
        "test_payloads_read": False,
        "counts": {
            "ibsr_development": sum(r["partition"] == "development" for r in records),
            "mrbrains_training_external": sum(r["partition"] == "external" for r in records),
        },
    }


def load_human(
    path: Path, *, dataset: str, subject: str, role: Literal["intensity", "labels"]
) -> Volume:
    if dataset not in ("ibsr-v2", "mrbrains13") or not subject.startswith(dataset):
        raise ValueError("Dataset namespace and subject identity mismatch")
    if dataset == "mrbrains13" and ("test" in path.parts or "training" not in path.parts):
        raise ValueError("Only MRBrainS labeled training partition is permitted")
    im: Any = nib.load(path)
    if dataset == "ibsr-v2" and not path.name.startswith(subject.split(":", 1)[1] + "_"):
        raise ValueError("IBSR filename and subject identity mismatch")
    if dataset == "mrbrains13" and path.parent.name != subject.split(":", 1)[1]:
        raise ValueError("MRBrainS directory and subject identity mismatch")
    frame = None
    if len(im.shape) == 4:
        if dataset != "ibsr-v2" or im.shape[3] != 1:
            raise ValueError("Only explicit IBSR singleton frame0 is supported")
        frame = 0
    if int(im.header["sform_code"]) == 0:
        raise ValueError("Coded native sform required")
    q, qc = im.get_qform(coded=True)
    s, sc = im.get_sform(coded=True)
    if dataset == "mrbrains13" and qc and sc and corner_displacement_mm(q, s, im.shape) > 0.5:
        raise ValueError("MRBrainS qform/sform discrepancy exceeds frozen tolerance")
    units = im.header.get_xyzt_units()[0]
    if dataset == "mrbrains13" and units != "mm":
        raise ValueError("MRBrainS declared millimetre units required")
    override = "mm" if dataset == "ibsr-v2" and units == "unknown" else None
    if dataset == "ibsr-v2":
        spacing = np.sort(np.array(im.header.get_zooms()[:3]))
        if not (
            np.isclose(spacing[-1], 1.5, atol=0.001)
            and np.all((spacing[:2] > 0.83) & (spacing[:2] < 1.001))
        ):
            raise ValueError(
                "IBSR spacing does not support the explicit published millimetre convention"
            )
    v = load_nifti(path, frame=frame, policy="sform", units_override=override, kind=role)
    metadata = {
        **v.metadata,
        "dataset": dataset,
        "subject": subject,
        "space": subject + "-native",
        "units_evidence": "published IBSR v2 spacing and matching native grid"
        if override
        else "coded NIfTI mm",
        "singleton_frame_policy": frame,
    }
    if role == "labels":
        data = v.array()
        if (
            not np.isfinite(data).all()
            or np.any(data < 0)
            or not np.equal(data, np.rint(data)).all()
        ):
            raise ValueError("Exact nonnegative integer reference codes required")
        allowed = set(range(4)) if dataset == "ibsr-v2" else set(MR_NAMES)
        if not set(np.unique(data)).issubset(allowed):
            raise ValueError("Unknown native tissue code")
        v = Volume(data.astype(np.int16), v.affine_m, role, metadata)
    return Volume(v.data, v.affine_m, role, metadata)


def align_t1(
    image: Volume, reference: Volume, *, dataset: str, maximum_mm: float = 0.05
) -> tuple[Volume, dict[str, Any]]:
    if image.metadata.get("subject") != reference.metadata.get("subject"):
        raise ValueError("Alignment mixes subject identities")
    if image.shape != reference.shape:
        raise ValueError("Unequal native dimensions; no assumed registration")
    difference = corner_displacement_mm(
        image.affine_m * 1000, reference.affine_m * 1000, image.shape
    )
    receipt = {
        "maximum_corner_displacement_mm": difference,
        "fitted_registration": False,
        "source_geometry": image.geometry(),
        "target_geometry": reference.geometry(),
        "policy": (
            "unchanged native reference; identity-world one-pass linear intensity resampling only"
        ),
    }
    if image.same_grid(reference):
        return image, {**receipt, "resampled": False}
    if dataset != "mrbrains13" or difference > maximum_mm:
        raise ValueError("Image/reference geometry mismatch exceeds frozen alignment policy")
    out = resample(image, reference, order=1)
    return out, {**receipt, "resampled": True, "resampling": out.metadata["resampling"]}


def mapped_reference(native: Volume, dataset: str) -> tuple[Volume, Volume]:
    values = require_labels(native)
    mapping = (
        {0: 0, 1: 1, 2: 2, 3: 3}
        if dataset == "ibsr-v2"
        else MR_MAPPING
        if dataset == "mrbrains13"
        else {}
    )
    if not mapping or not set(np.unique(values)).issubset(mapping):
        raise ValueError("Reference label ontology incompatible with declared dataset")
    labels = np.zeros(native.shape, dtype=np.uint8)
    for code, target in mapping.items():
        labels[values == code] = target
    valid = (
        ~np.isin(values, [7, 8]) if dataset == "mrbrains13" else np.ones(native.shape, dtype=bool)
    )
    return Volume(
        labels,
        native.affine_m,
        "labels",
        {**native.metadata, "mapping": mapping, "ontology": TISSUES},
    ), Volume(
        valid,
        native.affine_m,
        "labels",
        {
            "subject": native.metadata["subject"],
            "exclusion": "native7/8 CB/brainstem" if dataset == "mrbrains13" else "none",
        },
    )


def verify_inventory_inputs(inventory: dict[str, Any]) -> None:
    for record in inventory["files"]:
        if sha256(Path(record["path"])) != record["sha256"]:
            raise ValueError("Frozen input changed after inventory; evaluation refused")


def inventory_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if value.get("test_payloads_read") is not False:
        raise ValueError("Unverified test-partition exclusion")
    return dict(value)
