"""Explicit external fMRIPrep invocation; never install/pull tools or templates."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from soma.core.provenance import write_json
from soma.pipeline.derivatives import private_output


def external_preprocessing(
    raw: Path,
    output: Path,
    *,
    subject: str,
    template_cache: Path,
    work: Path,
    execute: bool = False,
    assets_verified: bool = False,
    offline_launcher: tuple[str, ...] = (),
) -> dict[str, Any]:
    executable = shutil.which("fmriprep")
    command = [
        *offline_launcher,
        executable or "fmriprep",
        str(raw),
        str(output),
        "participant",
        "--participant-label",
        subject,
        "--output-spaces",
        "T1w",
        "--fs-no-reconall",
        "--nthreads",
        "1",
        "--omp-nthreads",
        "1",
        "--notrack",
        "-w",
        str(work),
    ]
    result = {
        "available": bool(executable),
        "command": command,
        "execute_requested": execute,
        "automatic_install": False,
        "template_fetch_requested": False,
        "offline_launcher": list(offline_launcher),
        "template_cache": str(template_cache),
        "requires": "preinstalled tools/resources; caller must enforce external network policy",
    }
    if not execute:
        return result
    if not executable or not assets_verified or not template_cache.is_dir() or not offline_launcher:
        raise ValueError(
            "Installed fMRIPrep, local resources and explicit offline launcher required"
        )
    private_output(output)
    private_output(work)
    output.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    write_json(output / "soma-external-command.json", {**result, "version": version})
    environment = {**os.environ, "TEMPLATEFLOW_HOME": str(template_cache)}
    completed = subprocess.run(command, env=environment, check=False)
    return {
        **result,
        "version": version,
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
    }
