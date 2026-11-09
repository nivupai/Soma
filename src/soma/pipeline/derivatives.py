"""Exclusive BIDS derivative products and honest local schema validation."""

import importlib.metadata
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from bids import BIDSLayout

from soma.core.paths import output_repository
from soma.core.provenance import sha256, write_json
from soma.imaging.nifti import load_nifti, save_nifti
from soma.pipeline.contracts import InputRecord

TISSUE_LUT = (
    "index\tname\tabbreviation\tmapping\n"
    "0\tBackground\tBG\t0\n"
    "1\tCerebrospinal Fluid\tCSF\t3\n"
    "2\tGray Matter\tGM\t1\n"
    "3\tWhite Matter\tWM\t2\n"
)


def private_output(path: Path) -> None:
    repo = output_repository(path)
    resolved = path.resolve()
    if repo is not None:
        if not any(
            resolved.is_relative_to(repo / p) for p in ["reports", "data/derived", "derivatives"]
        ):
            raise ValueError(
                "MRI artifacts must stay in ignored reports, derived data or derivatives"
            )
        if subprocess.run(
            ["git", "check-ignore", "--quiet", str(resolved / "privacy-sentinel")], cwd=repo
        ).returncode:
            raise ValueError("MRI output Git exclusion is not active")


def initialize_dataset(output: Path, record: InputRecord) -> None:
    private_output(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "dataset_description.json"
    description: dict[str, Any] = {
        "Name": "Soma anatomical derivatives",
        "BIDSVersion": "1.11.2",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "Soma",
                "Version": importlib.metadata.version("soma-neuro"),
                "Description": (
                    "Research anatomical processing; not clinical/anatomical certification"
                ),
            }
        ],
        "SourceDatasets": [{"URL": (record.source_root or record.image.parent).resolve().as_uri()}],
    }
    if record.dataset_type == "bids":
        description["DatasetLinks"] = {
            "source": (record.source_root or record.image.parent).resolve().as_uri()
        }
    if path.exists():
        old = json.loads(path.read_text())
        if old != description:
            raise ValueError("Existing derivative dataset description conflicts; choose new output")
    else:
        with tempfile.TemporaryDirectory(dir=output, prefix=".soma-description-") as tmp:
            temporary = Path(tmp) / "description.json"
            temporary.write_text(json.dumps(description, indent=2))
            os.link(temporary, path)


def export_subject(
    output: Path,
    record: InputRecord,
    artifacts: dict[str, Any],
    run_identity: str,
    *,
    resume: bool = False,
) -> dict[str, Any]:
    initialize_dataset(output, record)
    parent = output / f"sub-{record.subject}"
    if record.session:
        parent = parent / f"ses-{record.session}"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / "anat"
    prefix = record.key
    for entity, bidsname in [("acquisition", "acq"), ("run", "run"), ("reconstruction", "rec")]:
        if entity in record.entities:
            value = str(record.entities[entity])
            if not re.fullmatch("[a-zA-Z0-9]+", value):
                raise ValueError("Invalid source derivative entity")
            prefix += f"_{bidsname}-{value}"
    source_uri = (
        "bids:source:" + record.image.resolve().relative_to(record.source_root.resolve()).as_posix()
        if record.dataset_type == "bids" and record.source_root
        else record.image.resolve().as_uri()
    )
    common = {
        "Sources": [source_uri],
        "SpatialReference": "orig",
        "Soma": {
            "RunIdentity": run_identity,
            "Origin": record.dataset_type,
            "SourceIdentity": record.receipt(),
            "Preprocessing": artifacts["preprocess_qc"],
            "Backend": artifacts["backend_qc"],
            "ParametersAreAnatomicalCertification": False,
        },
    }
    if target.exists():
        if not resume:
            raise FileExistsError("Duplicate derivative destination; explicit resume required")
        import numpy as np

        for p in target.glob("*.nii.gz"):
            side = json.loads(p.with_name(p.name[:-7] + ".json").read_text())
            if (
                side.get("Soma") != json.loads(json.dumps(common["Soma"]))
                or side.get("Sources") != common["Sources"]
                or side.get("SpatialReference") != "orig"
            ):
                raise ValueError("Published derivative provenance differs from resumed execution")
            expected = (
                artifacts["labels"]
                if "dseg" in p.name
                else artifacts["mask"]
                if "mask" in p.name
                else artifacts["processed"]
            )
            if expected is None:
                raise ValueError("Unexpected published mask")
            observed = load_nifti(p, kind=expected.kind)
            if not expected.same_grid(observed) or not np.array_equal(
                expected.array(), observed.array()
            ):
                raise ValueError("Published derivative content differs")
            if "dseg" in p.name:
                lut = p.with_name(p.name[:-7] + ".tsv")
                if not lut.is_file() or lut.read_text() != TISSUE_LUT:
                    raise ValueError("Published label mapping changed")
        if len(list(target.glob("*.nii.gz"))) != 2 + int(artifacts["mask"] is not None):
            raise ValueError("Incomplete derivative publication")
        return {
            "files": {
                str(p.relative_to(output)): sha256(p) for p in target.iterdir() if p.is_file()
            },
            "dataset_description_sha256": sha256(output / "dataset_description.json"),
            "run_identity": run_identity,
        }
    with tempfile.TemporaryDirectory(dir=parent, prefix=".soma-export-") as tmp:
        pending = Path(tmp) / "anat"
        pending.mkdir()
        products: list[tuple[str, Any, dict[str, Any]]] = [
            (
                "desc-preproc_T1w",
                artifacts["processed"],
                {"SkullStripped": bool(record.metadata.get("SkullStripped", False))},
            ),
            (
                "desc-multiotsu_dseg"
                if artifacts["backend_qc"]["backend"] == "Soma multi-Otsu"
                else "desc-segmentation_dseg",
                artifacts["labels"],
                {},
            ),
            ("desc-foreground_mask", artifacts["mask"], {"Type": "ROI"}),
        ]
        for suffix, image, extras in products:
            if image is None:
                continue
            stem = prefix + "_" + suffix
            save_nifti(image, pending / (stem + ".nii.gz"))
            write_json(pending / (stem + ".json"), {**common, **extras})
            if suffix.endswith("dseg"):
                (pending / (stem + ".tsv")).write_text(TISSUE_LUT)
        os.rename(pending, target)
    return {
        "files": {str(p.relative_to(output)): sha256(p) for p in target.iterdir() if p.is_file()},
        "dataset_description_sha256": sha256(output / "dataset_description.json"),
        "run_identity": run_identity,
    }


def validate_derivatives(root: Path, *, full: bool = True) -> dict[str, Any]:
    description = json.loads((root / "dataset_description.json").read_text())
    if (
        description.get("DatasetType") != "derivative"
        or not description.get("GeneratedBy")
        or not description.get("BIDSVersion")
    ):
        raise ValueError("Invalid derivative dataset description")
    if not all(g.get("Name") and g.get("Version") for g in description["GeneratedBy"]):
        raise ValueError("GeneratedBy needs tool/version")
    index = BIDSLayout(root, validate=False, is_derivative=True)
    files = list(root.rglob("*.nii.gz"))
    if not files:
        raise ValueError("No anatomical derivative images")
    for p in files:
        relative = p.relative_to(root).as_posix()
        indexed = index.get_file(str(p.resolve()))
        entities = {} if indexed is None else indexed.get_entities()
        if (
            not entities.get("subject")
            or entities.get("datatype") != "anat"
            or entities.get("suffix") not in ("T1w", "dseg", "mask")
        ):
            raise ValueError("Unrecognized anatomical derivative entities: " + relative)
        side = p.with_name(p.name[:-7] + ".json")
        metadata = json.loads(side.read_text())
        if "SpatialReference" not in metadata or not metadata.get("Sources"):
            raise ValueError("Derivative lacks spatial/source relationship")
        volume = load_nifti(
            p, kind="labels" if p.name.endswith(("dseg.nii.gz", "mask.nii.gz")) else "intensity"
        )
        if p.name.endswith("dseg.nii.gz") and not p.with_name(p.name[:-7] + ".tsv").is_file():
            raise ValueError("Explicit custom label LUT required")
        if volume.kind == "intensity" and not isinstance(metadata.get("SkullStripped"), bool):
            raise ValueError("Preprocessed T1w requires SkullStripped boolean")
    result: dict[str, Any] = {
        "structural_checks": "PASS",
        "images": len(files),
        "indexed_files": len(index.get(return_type="filename")),
        "full_schema_status": "INDETERMINATE",
        "BIDS_compliance_claimed": False,
    }
    if full:
        result["official_validator"] = official_validate(root)
        result["full_schema_status"] = result["official_validator"]["status"]
        result["BIDS_compliance_claimed"] = result["full_schema_status"] == "PASS"
    return result


def official_validate(root: Path) -> dict[str, Any]:
    """Official bundled validator with local schema and no network permission."""
    try:
        from deno import find_deno_bin

        package = importlib.metadata.distribution("bids-validator-deno")
        from bidsschematools.schema import load_schema

        schema = load_schema()
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "schema.json"
            schema_path.write_text(json.dumps(schema.to_dict()))
            command = [
                os.fsdecode(find_deno_bin()),
                "--allow-read",
                "--allow-env",
                "--allow-write",
                "--allow-run=git",
                str(package.locate_file("bids_validator_deno/bids-validator.js")),
                str(root.resolve()),
                "--schema",
                schema_path.as_uri(),
                "--format",
                "json",
            ]
            process = subprocess.run(command, cwd=tmp, text=True, capture_output=True, timeout=120)
        try:
            details = json.loads(process.stdout)
        except ValueError:
            details = {"stdout": process.stdout, "stderr": process.stderr}
        return {
            "status": "PASS" if process.returncode == 0 else "FAIL",
            "exit_code": process.returncode,
            "tool": "official bids-validator-deno",
            "package_version": package.version,
            "schema_version": str(schema["bids_version"]),
            "network_permission": False,
            "details": details,
        }
    except (ImportError, importlib.metadata.PackageNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"status": "INDETERMINATE", "diagnostic": str(exc), "network_permission": False}
