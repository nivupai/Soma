"""M33 inner-skull refinement: thick-slice training copies (development pools only).

For each training case, makes one degraded copy of the cropped 1 mm T1 that looks like a
clinical scan: slices averaged to 3 mm along the superior axis, a random contrast (gamma), a
smooth multiplicative bias field and Gaussian noise (seed fixed per case). SynthSeg and the
watershed are then run on the copy exactly as in ``scripts.dev_m33_crop``, and features are
extracted from the copy with CT targets from the same case's CT (which is not degraded).

Output: ``reports/milestone33/skull-dev-thick/cases/<case>/refine-features.npz`` in the same
format as the 1 mm features, so ``scripts.dev_m33_skull_improve`` can add them to training.
Nothing here touches CERMEP.

    python -m scripts.dev_m33_skull_thick --cases 1BA001 [...]
"""

import argparse
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from scripts.dev_m33_crop import ROOT as CROP
from scripts.dev_m33_skull import DATA, build_watershed, fs_env
from scripts.run_m33_segmentation import run_synthseg
from scripts.run_m33_skull_v2 import OFFSETS_MM, SYNTHSEG_CMD
from soma.anatomy.fs_skull import load_watershed, offset_mesh
from soma.anatomy.inner_skull_refine import features, t1_scale, targets
from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, superior_axis
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.synthseg import load_synthseg, to_native_grid

THICK = Path("reports/milestone33/skull-dev-thick")
SUBJECTS = Path("/Volumes/YOTUO/soma-data/fs-subjects-thick")
SLICE_MM = 3.0


def seed(case: str) -> int:
    return int(hashlib.sha256(f"thick:{case}".encode()).hexdigest()[:8], 16)


def degrade(t1: Volume, case: str) -> tuple[Volume, dict[str, Any]]:
    rng = np.random.default_rng(seed(case))
    data = t1.array(np.float64)
    axis, _ = superior_axis(t1)
    step = max(1, int(round(SLICE_MM / float(t1.spacing_m[axis] * 1000))))
    n = (data.shape[axis] // step) * step
    moved = np.moveaxis(data, axis, 0)[:n]
    thick = moved.reshape(n // step, step, *moved.shape[1:]).mean(axis=1)
    thick = np.moveaxis(thick, 0, axis)
    affine = np.array(t1.affine_m, dtype=float)
    # Block centre sits (step - 1) / 2 voxels along the axis from the first voxel of the block.
    affine[:3, 3] = affine[:3, 3] + affine[:3, axis] * (step - 1) / 2.0
    affine[:3, axis] = affine[:3, axis] * step
    positive = thick[thick > 0]
    hi = float(np.percentile(positive, 99.5)) if positive.size else 1.0
    gamma = float(np.exp(rng.uniform(np.log(0.7), np.log(1.4))))
    scaled = np.clip(thick / hi, 0, None) ** gamma
    grids = np.meshgrid(*[np.linspace(-1, 1, s) for s in scaled.shape], indexing="ij")
    coef = rng.normal(0, 0.08, size=(3, 2))  # linear + quadratic per axis, about +/-20 %
    log_bias = sum(c[0] * g + c[1] * (g**2 - 1 / 3) for c, g in zip(coef, grids, strict=True))
    biased = scaled * np.exp(log_bias)
    noise_sd = float(rng.uniform(0.01, 0.03))
    noisy = np.clip(biased + rng.normal(0, noise_sd, size=biased.shape) * (biased > 0.02), 0, None)
    out = (noisy * hi).astype(np.float32)
    receipt = {
        "slice_mm": SLICE_MM,
        "step_voxels": step,
        "axis": axis,
        "gamma": gamma,
        "bias_coefficients": coef.tolist(),
        "noise_sd_fraction": noise_sd,
        "seed": seed(case),
    }
    return Volume(out, affine, t1.kind, {**t1.metadata, "thick_copy": receipt}), receipt


def prepare(case: str, env: dict[str, str]) -> None:
    out = THICK / "cases" / case / "refine-features.npz"
    if out.exists():
        return
    path = THICK / "mri" / case / "mr.nii.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        thick, _ = degrade(load_nifti(CROP / "mri" / case / "mr.nii.gz"), case)
        save_nifti(thick, path)
    t1 = load_nifti(path)
    synth = load_synthseg(run_synthseg(SYNTHSEG_CMD, path, THICK / "synthseg" / case))
    synth_native, _ = to_native_grid(synth, t1)
    t1_scale(t1, synth_native)  # fails early if SynthSeg found no white matter
    subject = build_watershed(case, SUBJECTS, env, THICK / "mri")
    meshes = {b: offset_mesh(m, OFFSETS_MM[b]) for b, m in load_watershed(subject, case).items()}
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    inner = meshes["inner_skull"]
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        x=features(inner, t1, synth_native),
        y=targets(inner, truth.masks["inner_skull"]),
        region=region.contains_mm(inner.vertices.xyz * 1000),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", required=True)
    args = parser.parse_args()
    env = fs_env()
    for case in args.cases:
        prepare(case, env)
        print("done", case, flush=True)


if __name__ == "__main__":
    main()
