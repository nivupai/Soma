"""PyBIDS indexing and explicit legacy-to-workflow bridge, without source writes."""

import json
import re
from pathlib import Path
from typing import Any

from bids import BIDSLayout
from bids_validator import BIDSValidator

from soma.datasets.human_mri import access_metadata, align_t1, load_human
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.contracts import InputRecord


def inspect_bids(root: Path) -> dict[str, Any]:
    description = json.loads((root / "dataset_description.json").read_text())
    if (
        not isinstance(description.get("Name"), str)
        or not description["Name"]
        or not re.fullmatch(r"\d+\.\d+\.\d+", description.get("BIDSVersion", ""))
    ):
        raise ValueError("BIDS dataset_description requires Name and semantic BIDSVersion")
    if description.get("DatasetType", "raw") != "raw":
        raise ValueError(
            "Input must be an original raw BIDS dataset; use derivative inspection separately"
        )
    layout = BIDSLayout(root, validate=True, derivatives=False)
    images = layout.get(
        suffix="T1w", extension=[".nii", ".nii.gz"], return_type="object", scope="raw"
    )
    validator = BIDSValidator()
    rows = []
    for image in images:
        relative = Path(image.path).relative_to(root.resolve()).as_posix()
        if not validator.is_bids("/" + relative):
            raise ValueError("Invalid BIDS T1w filename/entities")
        entities = image.get_entities()
        if any(
            p.startswith("sub-") and p != "sub-" + str(entities.get("subject"))
            for p in Path(image.path).parts[:-1]
        ):
            raise ValueError("BIDS subject directory/filename entities disagree")
        if any(
            p.startswith("ses-") and p != "ses-" + str(entities.get("session"))
            for p in Path(image.path).parts[:-1]
        ):
            raise ValueError("BIDS session directory/filename entities disagree")
        if entities.get("datatype") != "anat" or not entities.get("subject"):
            raise ValueError("Invalid anatomical entities")
        rows.append(
            {"path": image.path, "entities": entities, "metadata": layout.get_metadata(image.path)}
        )
    return {
        "description": description,
        "subjects": layout.get_subjects(),
        "sessions": layout.get_sessions(),
        "T1w": rows,
        "derivatives": [
            str(p.parent) for p in (root / "derivatives").glob("*/dataset_description.json")
        ],
        "indexer": "PyBIDS",
        "validation_scope": (
            "PyBIDS indexing and Python filename checks; full schema validation separate"
        ),
    }


def select_bids(
    root: Path,
    participant: str,
    *,
    session: str | None = None,
    selection: str = "error",
    filters: dict[str, Any] | None = None,
) -> InputRecord:
    if selection not in ("error", "first-sorted"):
        raise ValueError("Unknown multiple-T1w selection policy")
    info = inspect_bids(root)
    requested = participant.removeprefix("sub-")
    rows = [r for r in info["T1w"] if r["entities"]["subject"] == requested]
    if session is not None:
        rows = [r for r in rows if r["entities"].get("session") == session.removeprefix("ses-")]
    if filters:
        rows = [
            r for r in rows if all(str(r["entities"].get(k)) == str(v) for k, v in filters.items())
        ]
    if not rows:
        raise ValueError("Requested subject/session/T1w acquisition not found")
    if len(rows) > 1 and selection == "error":
        raise ValueError(
            "Ambiguous session/acquisition: select explicit entities or first-sorted policy"
        )
    row = sorted(rows, key=lambda r: r["path"])[0]
    return InputRecord(
        Path(row["path"]),
        requested,
        row["entities"].get("session"),
        "bids",
        root,
        row["entities"],
        {**row["metadata"], "SomaSelection": selection},
    )


def legacy_records(ibsr_root: Path, mrbrains_root: Path, *, dataset: str) -> list[InputRecord]:
    if dataset not in ("ibsr", "mrbrains"):
        raise ValueError("Supported legacy datasets: ibsr or mrbrains")
    rows = []
    if dataset == "ibsr":
        notices = [p for p in ibsr_root.rglob("*") if p.name.lower() == "readme.txt"]
        if not any("Rohlfing" in p.read_text() for p in notices):
            raise ValueError("Local IBSR release notice required")
        for d in sorted(
            p for p in ibsr_root.rglob("*") if p.is_dir() and re.fullmatch(r"IBSR_\d+", p.name)
        ):

            def chosen(role: str, directory: Path = d) -> Path:
                candidates = [
                    directory / (directory.name + "_" + role + suffix)
                    for suffix in [".nii.gz", ".nii"]
                ]
                existing = [p for p in candidates if p.is_file()]
                if not existing:
                    raise ValueError("Missing IBSR native role: " + role)
                return existing[0]

            sid = "ibsr-v2:" + d.name
            rows.append(
                {
                    "dataset": "ibsr-v2",
                    "subject": sid,
                    "partition": "development",
                    "image": str(chosen("ana_strip")),
                    "reference": str(chosen("segTRI_ana")),
                    "space": sid + "-native",
                }
            )
    else:
        access_metadata(mrbrains_root, None)
        for reference in sorted((mrbrains_root / "training").rglob("LabelsForTraining.nii")):
            d = reference.parent
            if not re.fullmatch(r"\d+", d.name):
                raise ValueError("Unsupported MRBrainS training identity")
            sid = "mrbrains13-training:" + d.name
            rows.append(
                {
                    "dataset": "mrbrains13",
                    "subject": sid,
                    "partition": "external",
                    "image": str(d / "T1.nii"),
                    "reference": str(reference),
                    "testing_style_reference": str(d / "LabelsForTesting.nii"),
                    "space": sid + "-native",
                }
            )
    if not rows:
        raise ValueError("No permitted legacy subjects found")
    if len(rows) != len({r["subject"] for r in rows}):
        raise ValueError("Duplicate legacy subject identity")
    records = []
    for row in rows:
        label = (
            ("IBSR" + row["subject"].split("_")[-1])
            if dataset == "ibsr"
            else ("MRBrainS" + row["subject"].split(":")[-1])
        )
        records.append(
            InputRecord(
                Path(row["image"]),
                label,
                dataset_type="legacy",
                source_root=ibsr_root if dataset == "ibsr" else mrbrains_root,
                legacy=row,
                metadata={
                    "origin": "legacy non-BIDS; Soma-assigned derivative entity",
                    "source_identity": row["subject"],
                    "SkullStripped": dataset == "ibsr",
                    "Access": "user-authorized local research; no redistribution",
                },
            )
        )
    return records


def load_input(record: InputRecord, *, affine_policy: str = "error") -> Volume:
    if record.dataset_type == "legacy":
        assert record.legacy is not None
        row = record.legacy
        image = load_human(
            record.image, dataset=row["dataset"], subject=row["subject"], role="intensity"
        )
        native = load_human(
            Path(row["reference"]), dataset=row["dataset"], subject=row["subject"], role="labels"
        )
        image, alignment = align_t1(image, native, dataset=row["dataset"])
        return Volume(
            image.data,
            image.affine_m,
            "intensity",
            {**image.metadata, "pipeline_subject": record.subject, "legacy_alignment": alignment},
        )
    if affine_policy not in ("error", "sform", "qform"):
        raise ValueError("Explicit supported affine policy required")
    image = load_nifti(record.image, policy=affine_policy)  # type: ignore[arg-type]
    return Volume(
        image.data,
        image.affine_m,
        "intensity",
        {
            **image.metadata,
            "subject": record.subject,
            "space": record.key + "-native",
            "pipeline_subject": record.subject,
        },
    )
