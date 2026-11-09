"""Structured fMRIPrep provenance/geometry evidence, never filename-only validation."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from bids import BIDSLayout

from soma.core.provenance import sha256
from soma.experiments.cache import canonical_id
from soma.fmri.records import FunctionalRun, load_run
from soma.fmri.transform_audit import audit_transform
from soma.imaging.nifti import load_nifti
from soma.pipeline.cache import source_hash


@dataclass(frozen=True)
class PreprocessingBundle:
    raw_root: Path
    derivative_root: Path
    raw_bold: Path
    bold: Path
    mask: Path
    confounds: Path
    confound_json: Path
    t1: Path
    identity: dict[str, str]
    space: str
    transforms: tuple[dict[str, Any], ...] = ()
    qc_reports: tuple[Path, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)


def discover_bundle(
    raw: Path,
    derivatives: Path,
    *,
    subject: str,
    session: str,
    task: str,
    space: str,
    run: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> PreprocessingBundle:
    if not derivatives.is_dir():
        raise FileNotFoundError("Compatible fMRIPrep derivative directory unavailable")
    # Legacy ds000114 BIDSVersion1.0.0rc2 is indexed, not falsely certified current BIDS.
    original = BIDSLayout(raw, validate=False)
    layout = BIDSLayout(derivatives, validate=False, config=["bids", "derivatives"])
    entities = {"subject": subject, "session": session, "task": task}
    if run is not None:
        entities["run"] = run

    def one(index: Any, **kwargs: Any) -> Path:
        paths = index.get(return_type="filename", **kwargs)
        if len(paths) != 1:
            raise ValueError("Missing/ambiguous derivative/source asset: " + str(kwargs))
        return Path(paths[0])

    raw_bold = one(original, **entities, suffix="bold", extension=[".nii", ".nii.gz"])
    bold = one(
        layout,
        **entities,
        space=space,
        desc="preproc",
        suffix="bold",
        extension=[".nii", ".nii.gz"],
    )
    mask = one(layout, **entities, space=space, suffix="mask", extension=[".nii", ".nii.gz"])
    confounds = one(layout, **entities, desc="confounds", suffix="timeseries", extension=".tsv")
    t1s = layout.get(
        subject=subject,
        suffix="T1w",
        desc="preproc",
        extension=[".nii", ".nii.gz"],
        return_type="filename",
    )
    compatible = [
        p
        for p in t1s
        if not re.search(r"_space-|_ses-", Path(p).name) or f"_ses-{session}_" in Path(p).name
    ]
    if len(compatible) != 1:
        raise ValueError("A unique subject-native preprocessed T1w reference is required")
    evidence = evidence or {}
    ident = {
        "subject": subject,
        "session": session,
        "task": task,
        "run": str(original.parse_file_entities(raw_bold).get("run", "1")),
    }
    return PreprocessingBundle(
        raw,
        derivatives,
        raw_bold,
        bold,
        mask,
        confounds,
        confounds.with_suffix(".json"),
        Path(compatible[0]),
        ident,
        space,
        tuple(evidence.get("transforms", [])),
        tuple(derivatives.glob(f"sub-{subject}*.html")),
        evidence,
    )


def audit_preprocessing(bundle: PreprocessingBundle) -> dict[str, Any]:
    checks = []

    def record(name: str, kind: str, status: str, detail: Any) -> None:
        checks.append({"check": name, "evidence_class": kind, "status": status, "detail": detail})

    files = [
        bundle.raw_root / "dataset_description.json",
        bundle.derivative_root / "dataset_description.json",
        bundle.raw_bold,
        bundle.bold,
        bundle.mask,
        bundle.confounds,
        bundle.confound_json,
        bundle.t1,
        Path(str(bundle.bold).removesuffix(".nii.gz").removesuffix(".nii") + ".json"),
    ]
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        record("required_assets", "provenance", "INDETERMINATE", missing)
        return {
            "status": "INDETERMINATE",
            "eligible": False,
            "checks": checks,
            "anatomical_validity": "INDETERMINATE",
        }
    try:
        for path in files[2:]:
            for key, prefix in [
                ("subject", "sub"),
                ("session", "ses"),
                ("task", "task"),
                ("run", "run"),
            ]:
                if path == bundle.t1 and key in {"session", "task", "run"}:
                    continue
                found = re.findall(r"(?:^|[/_])" + prefix + r"-([A-Za-z0-9]+)", str(path))
                if any(value != bundle.identity[key] for value in found):
                    raise ValueError("Auxiliary file subject/session/task/run mismatch")
        record("subject_session_task_run", "metadata", "PASS", bundle.identity)
        original = BIDSLayout(bundle.raw_root, validate=False)
        raw_metadata = original.get_metadata(str(bundle.raw_bold.resolve()))
        desc = json.loads(files[1].read_text())
        generated = [
            g
            for g in desc.get("GeneratedBy", [])
            if g.get("Name", "").lower() == "fmriprep" and g.get("Version")
        ]
        record(
            "software_identity",
            "provenance",
            "PASS" if desc.get("DatasetType") == "derivative" and generated else "INDETERMINATE",
            generated,
        )
        sidecar = json.loads(files[-1].read_text())
        sources = sidecar.get("Sources", sidecar.get("RawSources", []))
        relative = bundle.raw_bold.resolve().relative_to(bundle.raw_root.resolve()).as_posix()
        raw_description = json.loads(files[0].read_text())
        doi = str(raw_description.get("DatasetDOI", "")).removeprefix("doi:")
        urls = [str(d.get("URL", "")) for d in desc.get("SourceDatasets", [])]
        dataset_link = any(
            url == bundle.raw_root.resolve().as_uri() or (doi and url.endswith(doi)) for url in urls
        )
        linked = any(str(item).endswith(relative) for item in sources) and dataset_link
        for item in sources:
            if str(item).startswith("bids:"):
                key = str(item).split(":")[1]
                root_link = desc.get("DatasetLinks", {}).get(key)
                if root_link != bundle.raw_root.resolve().as_uri():
                    linked = False
        record(
            "source_relationship",
            "provenance",
            "PASS" if linked else "INDETERMINATE",
            {"Sources": sources, "SourceDatasets": desc.get("SourceDatasets")},
        )
        raw_vol = load_nifti(bundle.raw_bold, frame=0)
        processed = load_nifti(bundle.bold, frame=0)
        mask = load_nifti(bundle.mask, kind="labels")
        t1 = load_nifti(bundle.t1)
        raw_image: Any = nib.load(bundle.raw_bold, mmap="r")
        image: Any = nib.load(bundle.bold, mmap="r")
        if image.ndim != 4 or raw_image.ndim != 4 or image.shape[3] != raw_image.shape[3]:
            raise ValueError(
                "BOLD count differs from source; temporal remapping/censoring unsupported"
            )
        tr = float(raw_metadata["RepetitionTime"])
        if sidecar.get("RepetitionTime") != tr or any(
            i.header.get_xyzt_units() != ("mm", "sec")
            or not np.isclose(float(i.header.get_zooms()[3]), tr, rtol=1e-5)
            for i in [image, raw_image]
        ):
            raise ValueError("TR or temporal/spatial units disagree")
        temporal_reference = bundle.evidence.get("slice_time_ref")
        temporal_valid = (
            isinstance(temporal_reference, (int, float))
            and np.isfinite(temporal_reference)
            and 0 <= temporal_reference <= 1
        )
        record(
            "slice_timing_reference",
            "provenance",
            "PASS" if temporal_valid else "INDETERMINATE",
            {
                "slice_time_ref": temporal_reference,
                "source": "explicit audited preprocessing settings",
            },
        )
        record(
            "TR_counts_units",
            "numerical",
            "PASS",
            {
                "TR_s": tr,
                "raw_volumes": raw_image.shape[3],
                "derivative_volumes": image.shape[3],
                "raw_geometry": raw_vol.geometry(),
                "geometry": processed.geometry(),
                "T1_geometry": t1.geometry(),
            },
        )
        if (
            not processed.same_grid(mask)
            or not np.isin(mask.array(), [0, 1]).all()
            or not np.any(mask.array())
        ):
            raise ValueError("Mask geometry/content differs from processed BOLD")
        if sidecar.get("SpatialReference") is None or bundle.space not in bundle.bold.name:
            raise ValueError("Explicit derivative spatial reference/space missing")
        record(
            "mask_spatial_reference",
            "numerical",
            "PASS",
            {
                "space": bundle.space,
                "reference": sidecar["SpatialReference"],
                "mask_voxels": int(np.sum(mask.array())),
            },
        )
        nuisance_metadata = json.loads(bundle.confound_json.read_text())
        run = load_run(
            bundle.bold,
            tr=tr,
            events=Path(
                original.get_nearest(
                    str(bundle.raw_bold),
                    suffix="events",
                    extension=".tsv",
                    strict=True,
                    ignore_strict_entities=["extension", "suffix"],
                    task=bundle.identity["task"],
                )
            ),
            confounds=bundle.confounds,
            mask=bundle.mask,
            space=bundle.space,
            preprocessing="validated",
            provenance={"source": str(bundle.raw_bold), "preprocessing_evidence": generated},
            **bundle.identity,
        )
        selected = [
            c
            for c in map(str, run.confounds.columns)
            if c.startswith(("trans_", "rot_", "framewise_", "dvars", "a_comp_cor", "non_steady"))
        ]
        undefined = [
            c
            for c in selected
            if not isinstance(nuisance_metadata.get(c), dict)
            or not any(nuisance_metadata[c].get(k) for k in ["Description", "LongName", "Method"])
        ]
        record(
            "confound_rows_definitions",
            "metadata",
            "PASS" if not undefined else "INDETERMINATE",
            {"rows": len(run.confounds), "undefined_columns": undefined},
        )
        transform_rows = [
            audit_transform(s, subject=bundle.identity["subject"]) for s in bundle.transforms
        ]
        required_pairs = {("boldref", "T1w")}
        if bundle.space != "T1w":
            required_pairs.add(("T1w", bundle.space))
        for transform in transform_rows:
            if transform["from_space"] == "boldref" and transform["to_space"] == "T1w":
                for declared, actual in [
                    (transform["source_grid"], raw_vol),
                    (transform["reference_grid"], t1),
                ]:
                    if tuple(declared["shape"]) != actual.shape or not np.allclose(
                        declared["voxel_to_RAS_m"], actual.affine_m, atol=1e-9, rtol=0
                    ):
                        raise ValueError(
                            "Transform source/reference grids do not match BOLD/T1 assets"
                        )
        pairs = {(r["from_space"], r["to_space"]) for r in transform_rows}
        complete = required_pairs.issubset(pairs) and all(
            r["landmark_status"] == "PASS" for r in transform_rows
        )
        record(
            "transform_chain",
            "numerical",
            "PASS" if complete else "INDETERMINATE",
            {"required_pairs": sorted(required_pairs), "transforms": transform_rows},
        )
        for t1_source in bundle.evidence.get("T1_sources", []):
            path = Path(t1_source)
            labels = re.findall(r"(?:^|[/_])sub-([A-Za-z0-9]+)", str(path))
            if any(label != bundle.identity["subject"] for label in labels):
                raise ValueError("Anatomical reference source belongs to another subject")
            if not path.resolve().is_relative_to(bundle.raw_root.resolve()):
                raise ValueError("Anatomical source must belong to the declared raw dataset")
        record(
            "anatomical_reference",
            "metadata",
            "PASS"
            if bundle.evidence.get("T1_sources")
            and all(Path(p).is_file() for p in bundle.evidence["T1_sources"])
            else "INDETERMINATE",
            {"path": str(bundle.t1), "source_declared": bundle.evidence.get("T1_sources")},
        )
        qc_review = bundle.evidence.get("visual_QC_review")
        record(
            "QC_report_review",
            "heuristic",
            "PASS" if qc_review and bundle.qc_reports else "INDETERMINATE",
            {"reports": [str(p) for p in bundle.qc_reports], "review": qc_review},
        )
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        record("consistency_failure", "metadata/numerical", "FAIL", str(exc))
    fingerprints = {str(p): sha256(p) for p in files}
    for spec in bundle.transforms:
        for key in ["path", "source_image", "reference"]:
            value = spec.get(key)
            if not isinstance(value, (str, Path)):
                continue
            p = Path(value)
            if p.is_file():
                fingerprints[str(p)] = sha256(p)
    for p in bundle.qc_reports:
        if p.is_file():
            fingerprints[str(p)] = sha256(p)
    for p in bundle.evidence.get("T1_sources", []):
        if Path(p).is_file():
            fingerprints[str(p)] = sha256(Path(p))
    # Include inherited acquisition/event metadata in the import fingerprint.
    for p in bundle.raw_root.rglob("*"):
        if p.is_file() and (p.suffix == ".json" or p.name.endswith("_events.tsv")):
            fingerprints[str(p)] = sha256(p)
    identity = canonical_id(
        {
            "files": fingerprints,
            "identity": bundle.identity,
            "space": bundle.space,
            "evidence": bundle.evidence,
            "source": source_hash(),
        }
    )
    status = (
        "FAIL"
        if any(c["status"] == "FAIL" for c in checks)
        else "INDETERMINATE"
        if any(c["status"] == "INDETERMINATE" for c in checks)
        else "PASS"
    )
    return {
        "status": status,
        "eligible": status == "PASS",
        "checks": checks,
        "fingerprints": fingerprints,
        "identity": identity,
        "source_tree_sha256": source_hash(),
        "anatomical_validity": "INDETERMINATE",
        "scope": "metadata/geometry/landmark/QC evidence; anatomical certification unsupported",
    }


def load_audited_run(bundle: PreprocessingBundle, receipt: dict[str, Any]) -> FunctionalRun:
    current = audit_preprocessing(bundle)
    if not current["eligible"] or current.get("identity") != receipt.get("identity"):
        raise ValueError("Preprocessing audit failed, incomplete or stale; raw modeling forbidden")
    raw = BIDSLayout(bundle.raw_root, validate=False)
    events = raw.get_nearest(
        str(bundle.raw_bold),
        suffix="events",
        extension=".tsv",
        strict=True,
        ignore_strict_entities=["extension", "suffix"],
        task=bundle.identity["task"],
    )
    return load_run(
        bundle.bold,
        tr=float(raw.get_metadata(str(bundle.raw_bold.resolve()))["RepetitionTime"]),
        events=Path(events),
        confounds=bundle.confounds,
        mask=bundle.mask,
        space=bundle.space,
        preprocessing="validated",
        provenance={
            "source": str(bundle.raw_bold),
            "preprocessing_evidence": current,
            "cross_session_alignment": bundle.evidence.get("cross_session_alignment"),
            "effect_scale_identity": bundle.evidence.get("effect_scale_identity"),
            "audit_identity": current["identity"],
        },
        **bundle.identity,
    )
