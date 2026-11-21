"""M33 skull v2 DEVELOPMENT harness: development cases only, never held-out cases.

Per case: build the FreeSurfer watershed BEM (conform, N3, normalise, mri_watershed), the CT
truth with the v2 cavity fix, and score each candidate method against it. Outputs go to the
ignored ``reports/milestone33/skull-dev``. Results here choose and tune the method; the sealed
v2 protocol then scores the held-out cases once.

    python -m scripts.dev_m33_skull --cases 1BA001 ... --fs-subjects /Volumes/X/fs-subjects
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from soma.anatomy.fs_skull import load_watershed, voxelize
from soma.anatomy.t1_skull import T1SkullParameters, estimate_t1_skull, mask_volume, pad
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
from soma.core.provenance import write_json
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.synthseg import load_synthseg

SPLIT = Path("configs/m33-skull-v2-split.json")
DATA = Path("data/external/synthrad2023/brain")
OUT = Path("reports/milestone33/skull-dev")
SYNTHSEG_CACHE = Path("reports/milestone33/skull/cases")


def fs_env() -> dict[str, str]:
    env = dict(os.environ)
    home = env.setdefault("FREESURFER_HOME", "/Applications/freesurfer/8.1.0")
    env.setdefault("FS_LICENSE", str(Path.home() / "Downloads" / "license.txt"))
    setup = subprocess.run(
        ["bash", "-c", f"source {home}/SetUpFreeSurfer.sh >/dev/null 2>&1; env -0"],
        capture_output=True,
        env=env,
        check=True,
    )
    for item in setup.stdout.split(b"\0"):
        if b"=" in item:
            k, v = item.decode().split("=", 1)
            env[k] = v
    return env


def build_watershed(case: str, subjects: Path, env: dict[str, str]) -> Path:
    subject = subjects / case
    if (subject / "bem" / "watershed" / f"{case}_outer_skin_surface").exists():
        return subject
    (subject / "mri").mkdir(parents=True, exist_ok=True)
    mri = subject / "mri"
    log = open(subject / "build.log", "w")  # noqa: SIM115
    run = {"env": env, "stdout": log, "stderr": subprocess.STDOUT, "check": True}
    subprocess.run(
        [
            "mri_convert",
            "--conform",
            str((DATA / case / "mr.nii.gz").resolve()),
            str(mri / "orig.mgz"),
        ],
        **run,  # type: ignore[arg-type]
    )
    subprocess.run(
        [
            "mri_nu_correct.mni",
            "--i",
            str(mri / "orig.mgz"),
            "--o",
            str(mri / "nu.mgz"),
            "--n",
            "1",
        ],
        cwd=mri,
        **run,  # type: ignore[arg-type]
    )
    subprocess.run(["mri_normalize", str(mri / "nu.mgz"), str(mri / "T1.mgz")], **run)  # type: ignore[arg-type]
    code = (
        "import mne; mne.bem.make_watershed_bem("
        f"{case!r}, subjects_dir={str(subjects)!r}, overwrite=True, verbose='ERROR')"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        **{**run, "env": {**env, "SUBJECTS_DIR": str(subjects)}},
    )  # type: ignore[arg-type]
    return subject


def watershed_estimate(
    subject: Path, case: str, like: Volume
) -> tuple[dict[str, Any], dict[str, Volume]]:
    meshes = load_watershed(subject, case)
    masks = {
        name: mask_volume(voxelize(mesh, like), like, boundary=name)
        for name, mesh in meshes.items()
    }
    return meshes, masks


def evaluate(case: str, subjects: Path, env: dict[str, str]) -> dict[str, Any]:
    out = OUT / case
    if (out / "dev-metrics.json").exists():
        return dict(json.loads((out / "dev-metrics.json").read_text()))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    t1 = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(t1, CTSkullParameters().padding_voxels)
    result: dict[str, Any] = {
        "case": case,
        "cavity_ml": float(
            truth.masks["inner_skull"].array().sum() * np.prod(like.spacing_m * 1000) / 1000
        ),
        "methods": {},
    }
    subject = build_watershed(case, subjects, env)
    ws_meshes, ws_masks = watershed_estimate(subject, case, like)
    result["methods"]["watershed"] = score_case(ws_meshes, ws_masks, truth, region)
    synth = SYNTHSEG_CACHE / case / "synthseg.nii.gz"
    if synth.exists():
        base = estimate_t1_skull(t1, load_synthseg(synth), parameters=T1SkullParameters())
        result["methods"]["t1_baseline"] = score_case(base.meshes, base.masks, truth, region)
    result["wall_s"] = time.perf_counter() - t0
    write_json(out / "dev-metrics.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--fs-subjects", type=Path, required=True)
    args = parser.parse_args()
    development = set(json.loads(SPLIT.read_text())["development"])
    cases = args.cases or sorted(development)
    if not set(cases) <= development:
        raise SystemExit("Development harness refuses held-out cases")
    env = fs_env()
    for case in cases:
        try:
            r = evaluate(case, args.fs_subjects, env)
            print("done", case, round(r["wall_s"]), flush=True)
        except Exception as exc:  # reported per case
            print("FAIL", case, type(exc).__name__, exc, flush=True)


if __name__ == "__main__":
    main()
