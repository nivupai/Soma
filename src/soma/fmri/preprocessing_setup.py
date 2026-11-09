"""Read-only BIDS/resource inventory and exact, gated single-participant plan."""

import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import nibabel as nib
import yaml
from bids import BIDSLayout

from soma.anatomy.reporting import AnatomyReport
from soma.core.provenance import sha256, write_json
from soma.pipeline.derivatives import official_validate, private_output


def readiness(
    config_path: Path,
    output: Path,
    *,
    runtime: dict[str, Any] | None = None,
    image_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text())
    raw = Path(cfg["raw"]).resolve()
    private_output(output)
    report = AnatomyReport(output, cfg)
    layout = BIDSLayout(raw, validate=False)
    inventory = {}
    for suffix in ["bold", "T1w", "phasediff", "fieldmap", "epi", "events"]:
        filters = {"subject": cfg["subject"]}
        if suffix in ["bold", "events"]:
            filters["task"] = cfg["task"]
        if suffix == "events":
            # Dataset-level events are inherited by subjects and have no subject entity.
            filters.pop("subject")
        candidates = layout.get(suffix=suffix, return_type="filename", **filters)
        inventory[suffix] = [
            name
            for name in candidates
            if layout.parse_file_entities(name).get("subject") in {None, cfg["subject"]}
        ]
    acquisition = []
    for name in inventory["bold"]:
        image: Any = nib.load(name, mmap="r")
        entities = layout.parse_file_entities(name)
        acquisition.append(
            {
                "path": name,
                "entities": entities,
                "shape": image.shape,
                "header_TR_s": float(image.header.get_zooms()[3]),
                "units": image.header.get_xyzt_units(),
                "metadata": layout.get_metadata(name),
                "sha256": sha256(Path(name)),
            }
        )
    with report.stage("official_BIDS_validation"):
        validation = official_validate(raw)
    write_json(output / "BIDS-validation.json", validation)
    transforms = [str(p) for p in raw.rglob("*_xfm.*")]
    confounds = [str(p) for p in raw.rglob("*confounds*") if p.is_file()]
    derivatives = [str(p.parent) for p in (raw / "derivatives").glob("*/dataset_description.json")]
    license_candidates = [
        Path(os.environ.get("FS_LICENSE", "__not_set__")),
        Path.home() / ".licenses/freesurfer/license.txt",
        Path.home() / ".freesurfer/license.txt",
    ]
    license_path = next((p.resolve() for p in license_candidates if p.is_file()), None)
    template_root = Path(
        os.environ.get("TEMPLATEFLOW_HOME", str(Path.home() / ".cache/templateflow"))
    )
    templates = {
        name: {
            "directory_present": (template_root / name).is_dir(),
            "nonempty_files": sum(
                p.is_file() and p.stat().st_size > 0 for p in (template_root / name).rglob("*")
            )
            if (template_root / name).is_dir()
            else 0,
        }
        for name in ["tpl-OASIS30ANTs", "tpl-MNI152NLin2009cAsym", "tpl-MNI152NLin6Asym"]
    }
    try:
        memory = int(
            subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL
            )
        )
    except (OSError, ValueError, subprocess.CalledProcessError):
        memory = None
    disk = shutil.disk_usage(raw)
    runtime = runtime or {"server_available": False, "reason": "runtime availability not proven"}
    image_manifest = image_manifest or {}
    if memory is None and isinstance(runtime.get("host_memory_bytes"), int):
        memory = runtime["host_memory_bytes"]
    blockers = []
    if validation["status"] != "PASS":
        blockers.append("untouched input subset has not passed current official BIDS validation")
    if len(inventory["bold"]) != 2 or len(inventory["T1w"]) != 2:
        blockers.append("selected two-session pilot incomplete")
    sessions = {str(r["entities"].get("session")) for r in acquisition}
    if sessions != set(cfg["sessions"]):
        blockers.append("BOLD sessions differ from frozen plan")
    if not runtime.get("server_available"):
        blockers.append("Docker daemon unavailable; local image/VM architecture/RAM unverified")
    if not image_manifest.get("local_image_available", False):
        blockers.append("pinned image not verified locally; no image pull performed")
    if license_path is None:
        blockers.append("FreeSurfer license unavailable; --fs-no-reconall is not a license waiver")
    if any(not value["nonempty_files"] for value in templates.values()):
        blockers.append("required TemplateFlow/anatomical assets absent or unverified")
    if memory is None or memory < cfg["memory_mb"] * 1024**2:
        blockers.append("host memory unknown or below requested limit")
    if disk.free < 30 * 1024**3:
        blockers.append("less than30GiB free workspace")
    filter_file = {
        "bold": {"task": cfg["task"], "session": cfg["sessions"]},
        "t1w": {"session": cfg["sessions"]},
    }
    write_json(output / "bids-filter.json", filter_file)
    # Execution is never launched by this inventory. --pull=never and --network=none
    # make missing resources fail, not fetch. Files/directories must be staged first.
    image_ref = (
        cfg["image"]
        if not image_manifest.get("digest")
        else cfg["image"].split(":")[0] + "@" + image_manifest["digest"]
    )
    license_mount = license_path or (Path.home() / ".licenses/freesurfer/license.txt")
    command = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--network=none",
        "--platform",
        cfg["platform"],
        "--memory",
        str(cfg["memory_mb"]) + "m",
        "--cpus",
        str(cfg["threads"]),
        "-v",
        str(raw) + ":/data:ro",
        "-v",
        str(Path(cfg["output"]).resolve()) + ":/out",
        "-v",
        str(Path(cfg["work"]).resolve()) + ":/work",
        "-v",
        str(template_root.resolve()) + ":/templates:ro",
        "-v",
        str(license_mount) + ":/opt/license.txt:ro",
        "-v",
        str((output / "bids-filter.json").resolve()) + ":/config/bids-filter.json:ro",
        "-e",
        "TEMPLATEFLOW_HOME=/templates",
        image_ref,
        "/data",
        "/out",
        "participant",
        "--participant-label",
        cfg["subject"],
        "--bids-filter-file",
        "/config/bids-filter.json",
        "--output-spaces",
        *cfg["output_spaces"],
        "--subject-anatomical-reference",
        "unbiased",
        "--fs-no-reconall",
        "--fs-license-file",
        "/opt/license.txt",
        "--nthreads",
        str(cfg["threads"]),
        "--omp-nthreads",
        "1",
        "--mem-mb",
        str(cfg["memory_mb"]),
        "--notrack",
        "-w",
        "/work",
    ]
    (output / "command.sh").write_text(
        "#!/bin/sh\n# PLAN ONLY: resolve blockers and review before executing.\n"
        + shlex.join(command)
        + "\n"
    )
    write_json(
        output / "private-inventory.json",
        {
            "files": inventory,
            "acquisitions": acquisition,
            "transforms": transforms,
            "confounds": confounds,
            "derivatives": derivatives,
        },
    )
    return report.finish(
        {
            "status": "ready-for-explicit-execution" if not blockers else "blocked",
            "executed": False,
            "BIDS_status": validation["status"],
            "raw_BOLD": len(inventory["bold"]),
            "raw_T1w": len(inventory["T1w"]),
            "fieldmap_files": sum(len(inventory[s]) for s in ["phasediff", "fieldmap", "epi"]),
            "derivative_directories": len(derivatives),
            "transform_files": len(transforms),
            "confound_files": len(confounds),
            "host": {
                "system": platform.system(),
                "architecture": platform.machine(),
                "memory_bytes": memory,
                "disk_free_bytes": disk.free,
            },
            "runtime": runtime,
            "image": image_manifest,
            "license_present": license_path is not None,
            "template_assets": templates,
            "blockers": blockers,
            "command": command,
            "automatic_downloads_or_launches": False,
            "architecture_note": "ARM host needs verified amd64 emulation; performance unknown",
        }
    )
