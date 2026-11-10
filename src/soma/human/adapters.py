"""Explicit cached datasets only; private source mappings never become portable identities."""

import json
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd
from bids import BIDSLayout

from soma.core.provenance import sha256
from soma.datasets.eegbci import event_meanings, load_recording, recording_path
from soma.datasets.human_mri import nifti_metadata
from soma.human.model import Identity, pseudonym, validate_cohort
from soma.protocol.model import ProtocolError


@dataclass(frozen=True)
class Selection:
    identity: Identity
    root: Path
    subject: str
    files: tuple[tuple[str, Path], ...]
    hashes: tuple[tuple[str, str], ...]
    facts_json: bytes
    key: bytes | None = dataclass_field(default=None, repr=False, compare=False)

    def facts(self) -> dict[str, Any]:
        return dict(json.loads(self.facts_json))

    def verify_inputs(self) -> None:
        person = self.identity.document()
        if (
            self.key is None
            or pseudonym(person["dataset"], self.subject, self.key) != person["subject"]
        ):
            raise ProtocolError("Private participant mapping does not match scoped identity")
        if person["dataset"] == "eegmmidb":
            expected = recording_path(self.root, int(self.subject), int(person["run"]))
            if dict(self.files).get("image") != expected:
                raise ProtocolError("EEG recording path does not match participant/run")
        actual = dict(self.hashes)
        for role, path in self.files:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self.root.resolve(strict=True)):
                raise ProtocolError("Source path escapes configured dataset root")
            if role not in actual or sha256(resolved) != actual[role]:
                raise ProtocolError("Source input changed since identity inspection")


def identity(
    dataset: str,
    version: str,
    subject: str,
    key: bytes,
    *,
    modality: str,
    task: str,
    hashes: list[str],
    session: str | None = None,
    run: str | None = None,
    partition: str = "development",
    acquisition: dict[str, Any] | None = None,
    spatial: dict[str, Any] | None = None,
    temporal: dict[str, Any] | None = None,
) -> Identity:
    return Identity.from_dict(
        {
            "schema": "soma.human.identity/1.0.0",
            "dataset": dataset,
            "version": version,
            "subject": pseudonym(dataset, subject, key),
            "session": session,
            "task": task,
            "run": run,
            "acquisition": None,
            "modality": modality,
            "partition": partition,
            "acquisition_metadata": acquisition or {},
            "spatial_reference": spatial,
            "temporal_reference": temporal,
            "evidence": hashes,
            "availability": "AVAILABLE",
            "chronology": None,
            "consent_evidence": "NOT_PROVIDED",
        }
    )


def eeg(root: Path, subject: int, run: int, key: bytes) -> Selection:
    if type(subject) is not int or type(run) is not int:
        raise ProtocolError("Integer subject/run selectors required; booleans are ambiguous")
    path = recording_path(root, subject, run)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ProtocolError("Dataset root escape")
    raw, meta = load_recording(root, subject, run)
    try:
        sfreq = float(raw.info["sfreq"])
        samples = int(raw.n_times)
    finally:
        raw.close()
    meanings = event_meanings(run)
    task = (
        "unilateral-imagery"
        if run in [4, 8, 12]
        else "unilateral-movement"
        if run in [3, 7, 11]
        else "bilateral-imagery"
        if run in [6, 10, 14]
        else "bilateral-movement"
        if run in [5, 9, 13]
        else "baseline"
    )
    digest = sha256(path)
    person = identity(
        "eegmmidb",
        "1.0.0",
        str(subject),
        key,
        modality="EEG",
        task=task,
        run=str(run),
        hashes=[digest],
        acquisition={"channels": meta["n_eeg_channels"], "sfreq_hz": sfreq, "samples": samples},
        temporal={"unit": "s", "fs_hz": sfreq},
    )
    facts = {
        "events": meanings,
        "source_identity": "documented dataset path and EDF header/events; not biometric identity",
        "session": "not provided by this release; null",
        "preprocessing": "raw",
        "license_from_adapter": "ODC-By-1.0",
    }
    return Selection(
        person,
        root,
        str(subject),
        (("image", path),),
        (("image", digest),),
        json.dumps(facts).encode(),
        key=key,
    )


def one(root: Path, pattern: str) -> Path:
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise ProtocolError("Missing or ambiguous explicitly paired resource")
    return matches[0]


def role_file(root: Path, stem: str) -> Path:
    matches = list(root.glob(stem + ".nii*"))
    if any(not p.resolve(strict=True).is_relative_to(root.resolve(strict=True)) for p in matches):
        raise ProtocolError("MRI role resource escapes subject directory")
    if len(matches) == 1:
        return matches[0]
    raw, compressed = root / (stem + ".nii"), root / (stem + ".nii.gz")
    if set(matches) == {raw, compressed}:
        import gzip
        import hashlib

        with gzip.open(compressed, "rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum == sha256(raw):
            return compressed
    raise ProtocolError("Conflicting duplicate MRI role resources")


def mri(root: Path, dataset: str, subject: str, key: bytes) -> Selection:
    if dataset == "ibsr-v2":
        if not re.fullmatch(r"IBSR_\d{2}", subject) or not 1 <= int(subject[-2:]) <= 18:
            raise ProtocolError("Invalid IBSR subject")
        folder = one(root, "**/" + subject)
        if not folder.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
            raise ProtocolError("Subject directory escapes dataset root")
        image = role_file(folder, subject + "_ana_strip")
        reference = role_file(folder, subject + "_segTRI_ana")
        version = "v2-stripped"
        partition = "development"
    elif dataset == "mrbrains13":
        if not re.fullmatch(r"\d+", subject) or not 1 <= int(subject) <= 5:
            raise ProtocolError("Invalid training identifier")
        from soma.datasets.human_mri import access_metadata

        access_metadata(root, None)
        folder = one(root, "training/**/" + subject)
        if not folder.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
            raise ProtocolError("Training subject directory escapes dataset root")
        image = one(folder, "T1.nii")
        reference = one(folder, "LabelsForTraining.nii")
        version = "13-training"
        partition = "training"
    else:
        raise ProtocolError("Unsupported human structural dataset")
    files = (("image", image), ("reference", reference))
    if any(not p.resolve(strict=True).is_relative_to(root.resolve(strict=True)) for _, p in files):
        raise ProtocolError("Source resource escapes dataset root")
    hashes = tuple((k, sha256(v)) for k, v in files)
    if hashes[0][1] == hashes[1][1]:
        raise ProtocolError("Reference used as prediction input")
    geometry = {}
    for role, path in files:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ProtocolError("Dataset root escape")
        meta = nifti_metadata(path)
        meta.pop("path")
        geometry[role] = meta
    person = identity(
        dataset,
        version,
        subject,
        key,
        modality="MRI",
        task="structural",
        hashes=[h for _, h in hashes],
        partition=partition,
        spatial={"frame": "native-RAS", "units": "m in Soma; header units recorded"},
    )
    facts = {
        "geometry": geometry,
        "reference_labels_available": True,
        "ontology": {0: "background", 1: "CSF", 2: "GM", 3: "WM"}
        if dataset == "ibsr-v2"
        else {
            0: "background",
            1: "cortical GM",
            2: "basal ganglia",
            3: "WM",
            4: "WM lesions",
            5: "CSF",
            6: "ventricles",
            7: "cerebellum",
            8: "brainstem",
        },
        "mask_provenance": (
            "provided upstream skull-stripped input; not independent skull/scalp validation"
        ),
        "brain_mask_available": bool(list(folder.glob("*_ana_brainmask.nii*"))),
        "preprocessing": "upstream anatomical release; checked again by existing M11 loader",
        "holdout_status": "previously inspected development/evaluation data; never a fresh holdout",
    }
    return Selection(person, root, subject, files, hashes, json.dumps(facts).encode(), key=key)


def bids_fmri(root: Path, subject: str, key: bytes) -> list[Selection]:
    for resource in root.rglob("*"):
        if resource.is_symlink() and not resource.resolve(strict=True).is_relative_to(
            root.resolve(strict=True)
        ):
            raise ProtocolError("BIDS symlink escapes configured root")
    desc = json.loads((root / "dataset_description.json").read_text())
    if desc.get("DatasetDOI") != "doi:10.18112/openneuro.ds000114.v1.0.2":
        raise ProtocolError("Unknown BIDS release identity")
    layout = BIDSLayout(root, validate=False)
    rows = []
    for image in layout.get(
        subject=subject,
        task="fingerfootlips",
        suffix="bold",
        extension=["nii", "nii.gz"],
        return_type="object",
    ):
        entities = image.get_entities()
        for prefix, field in [("sub-", "subject"), ("ses-", "session")]:
            directories = [
                p[len(prefix) :] for p in Path(image.path).parts[:-1] if p.startswith(prefix)
            ]
            if directories != [str(entities.get(field))]:
                raise ProtocolError("BIDS directory/entity mismatch")
        meta = layout.get_metadata(image.path)
        if re.sub(r"[^a-z]", "", str(meta.get("TaskName", "")).lower()) != "fingerfootlips":
            raise ProtocolError("Task metadata mismatch")
        tr = float(meta["RepetitionTime"])
        header: Any = nib.load(image.path)
        if len(header.shape) != 4 or not np.isfinite(tr) or tr <= 0:
            raise ProtocolError("Invalid BOLD dimensions/TR")
        events = layout.get_nearest(
            image.path,
            suffix="events",
            extension=".tsv",
            strict=True,
            ignore_strict_entities=["extension", "suffix"],
            task="fingerfootlips",
        )
        if not events:
            raise ProtocolError("Missing matched task events")
        table = pd.read_csv(events, sep="\t")
        values = table[["onset", "duration"]].to_numpy(float)
        if (
            not len(values)
            or not np.isfinite(values).all()
            or (values < 0).any()
            or (values.sum(axis=1) > tr * header.shape[3]).any()
        ):
            raise ProtocolError("Invalid event timing")
        t1s = layout.get(
            subject=subject,
            session=entities["session"],
            suffix="T1w",
            return_type="filename",
            extension=["nii", "nii.gz"],
        )
        files = [
            ("image", Path(image.path)),
            ("events", Path(events)),
            ("description", root / "dataset_description.json"),
        ]
        if len(t1s) == 1:
            files.append(("structural", Path(t1s[0])))
        hashes = tuple((k, sha256(p)) for k, p in files)
        person = identity(
            "ds000114",
            "1.0.2",
            subject,
            key,
            modality="fMRI",
            task="fingerfootlips",
            session=entities["session"],
            run=str(entities["run"]) if "run" in entities else None,
            hashes=[h for _, h in hashes],
            temporal={"tr_s": tr, "n_scans": header.shape[3]},
            spatial={"frame": "native-scanner", "transform_verified": False},
        )
        facts = {
            "preprocessing": "RAW_ONLY",
            "structural_session_match": len(t1s) == 1,
            "events_count": len(table),
            "event_conditions": sorted(table.trial_type.unique().tolist()),
            "bids_validation": "legacy 1.0.0rc2 indexed; not certified current BIDS",
            "derivative_candidates": len(list(root.glob("derivatives/**/*desc-preproc_bold.nii*"))),
            "compatible_preprocessing_evidence": False,
            "transform_provenance": "NOT_PROVIDED",
            "chronology": "session labels preserved; acquisition order not verified",
        }
        rows.append(
            Selection(
                person, root, subject, tuple(files), hashes, json.dumps(facts).encode(), key=key
            )
        )
    validate_cohort([r.identity for r in rows])
    return rows
