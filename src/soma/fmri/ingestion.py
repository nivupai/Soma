"""Explicit raw versus preprocessed BIDS selection using existing PyBIDS tooling."""

import json
from pathlib import Path
from typing import Any

from bids import BIDSLayout

from soma.fmri.records import FunctionalRun, load_run
from soma.pipeline.ingestion import inspect_bids


def inspect_functional(root: Path) -> dict[str, Any]:
    base = inspect_bids(root)
    layout = BIDSLayout(root, validate=True, derivatives=False)
    bolds = layout.get(suffix="bold", extension=["nii", "nii.gz"], return_type="object")
    rows = []
    for image in bolds:
        rows.append(
            {
                "path": image.path,
                "entities": image.get_entities(),
                "metadata": layout.get_metadata(image.path),
            }
        )
    return {
        **base,
        "BOLD": rows,
        "events": layout.get(suffix="events", extension="tsv", return_type="filename"),
        "transforms": [str(p) for p in root.rglob("*_xfm.*")],
        "preprocessing_inferred": False,
        "warning": "Raw BIDS identity does not imply motion/distortion correction",
    }


def select_run(
    root: Path,
    *,
    subject: str,
    task: str,
    session: str | None = None,
    run: str | None = None,
    space: str | None = None,
    derivatives: Path | None = None,
    preprocessing_evidence: dict[str, Any] | None = None,
    mask: Path | None = None,
    exploratory_raw: bool = False,
) -> FunctionalRun:
    inspect_bids(root)
    raw = BIDSLayout(root, validate=True)
    selected = (
        BIDSLayout(derivatives, validate=False, config=["bids", "derivatives"])
        if derivatives
        else raw
    )
    query: dict[str, Any] = {
        "subject": subject,
        "task": task,
        "suffix": "bold",
        "extension": [".nii", ".nii.gz"],
    }
    if session is not None:
        query["session"] = session
    if run is not None:
        query["run"] = run
    if space is not None:
        query["space"] = space
    if derivatives:
        query["desc"] = "preproc"
    images = selected.get(return_type="object", **query)
    if len(images) != 1:
        raise ValueError("Missing or ambiguous BOLD subject/session/run/space; select explicitly")
    image = images[0]
    entities = image.get_entities()
    for prefix, key in [("sub-", "subject"), ("ses-", "session")]:
        if any(
            part.startswith(prefix) and part != prefix + str(entities.get(key))
            for part in Path(image.path).parts[:-1]
        ):
            raise ValueError("BIDS directory and image identity mismatch")
    if derivatives:
        desc = json.loads((derivatives / "dataset_description.json").read_text())
        if (
            desc.get("DatasetType") != "derivative"
            or not desc.get("GeneratedBy")
            or not preprocessing_evidence
        ):
            raise ValueError(
                "Preprocessed derivatives require GeneratedBy and explicit preprocessing evidence"
            )
    elif not exploratory_raw:
        raise ValueError(
            "Raw BOLD rejected: compatible externally preprocessed derivatives required"
        )
    exact = {
        k: entities[k]
        for k in ["subject", "session", "task", "run", "acquisition"]
        if k in entities
    }
    candidates = raw.get(
        suffix="bold", extension=[".nii", ".nii.gz"], return_type="object", **exact
    )
    if len(candidates) != 1:
        raise ValueError("Original raw image identity ambiguous or absent")
    original = candidates[0]
    metadata = raw.get_metadata(original.path)
    if "RepetitionTime" not in metadata:
        raise ValueError("BOLD acquisition RepetitionTime metadata missing")
    events = raw.get_nearest(
        original.path,
        suffix="events",
        extension=".tsv",
        strict=True,
        ignore_strict_entities=["extension", "suffix"],
        task=task,
    )
    if not events:
        raise ValueError("BIDS events.tsv missing for requested run")
    confounds = None
    if derivatives:
        matches = selected.get(
            suffix="timeseries", desc="confounds", extension=".tsv", return_type="filename", **exact
        )
        if len(matches) != 1:
            raise ValueError("A unique aligned confounds table is required for preprocessed input")
        confounds = Path(matches[0])
        if mask is None:
            matches = selected.get(
                suffix="mask",
                extension=[".nii", ".nii.gz"],
                return_type="filename",
                **exact,
                **({"space": space} if space else {}),
            )
            if len(matches) == 1:
                mask = Path(matches[0])
    if mask is None:
        raise ValueError("Explicit functional-space brain/ROI mask required")
    if "space" not in entities and derivatives and space is None:
        raise ValueError("Derivative spatial identity must be explicit, not inferred from shape")
    return load_run(
        Path(image.path),
        tr=float(metadata["RepetitionTime"]),
        subject=subject,
        session=str(entities.get("session", "none")),
        task=task,
        run=str(entities.get("run", "1")),
        space=space or str(entities.get("space", subject + "-native-bold")),
        events=Path(events),
        confounds=confounds,
        mask=mask,
        preprocessing="validated" if derivatives else "unvalidated-educational",
        provenance={
            "source": original.path,
            "source_root": str(root.resolve()),
            "subject": subject,
            "acquisition": metadata,
            "entities": entities,
            "preprocessing_evidence": preprocessing_evidence,
            "derivative_root": None if derivatives is None else str(derivatives.resolve()),
        },
    )


def inspect_matched_dataset(root: Path, subject: str) -> dict[str, Any]:
    """ds000117 adapter inventories modalities without inventing a visit mapping."""
    info = inspect_functional(root)
    files = list((root / ("sub-" + subject)).rglob("*"))
    eeg = [str(p) for p in files if p.is_file() and ("_eeg." in p.name or "_meg.fif" in p.name)]
    bold = [r for r in info["BOLD"] if r["entities"].get("subject") == subject]
    return {
        "subject": subject,
        "BOLD": bold,
        "EEG_or_MEG_with_possible_EEG": eeg,
        "matched_analysis_ready": False,
        "required": [
            "within-release identity",
            "EEG channel inspection",
            "visit mapping",
            "task provenance",
            "validated transforms",
            "compatible ROI ontology",
        ],
        "simultaneous_assumed": False,
    }
