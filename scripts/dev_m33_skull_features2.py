"""M33 inner-skull refinement: extra MRI-only per-vertex features (development pools only).

Adds to the v3.1 features (``refine-features.npz``, unchanged) a second file
``refine-features2.npz`` per case with, for the same calibrated inner-skull vertices:

- long profile: T1 / WM at -20..-11 and +11..+20 mm along the outward normal (20 columns);
- WM-CSF scaled profile: (T1 - CSF) / (WM - CSF) at -10..+10 mm (21), so contrast differences
  between scanners and centres cancel to first order (SynthSeg WM 2/41, CSF 4/43/24);
- tissue-distance profiles: signed distance to SynthSeg brain tissue (labels > 0 except CSF 24)
  and to extracerebral CSF (24) at -10..+10 mm in 2 mm steps (2 x 11);
- shape: mean-curvature proxy at 1-ring and 3-ring scale (2);
- context: distance from each vertex to the calibrated watershed outer skull and scalp
  meshes (2), and the vertex's height along the superior axis relative to the mesh centre (1).

Uses only the MRI, SynthSeg and the watershed meshes already built by
``scripts.dev_m33_crop prepare``; CT is not read. Nothing here touches CERMEP.

    python -m scripts.dev_m33_skull_features2 --cases 1BA001 [...]
"""

import argparse
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from scripts.dev_m33_crop import ROOT, SUBJECTS
from scripts.run_m33_skull_v2 import OFFSETS_MM
from soma.anatomy.fs_skull import load_watershed, offset_mesh
from soma.anatomy.inner_skull_refine import _sample, outward_normals, signed_distance_mm, t1_scale
from soma.imaging.nifti import load_nifti
from soma.pipeline.synthseg import load_synthseg, to_native_grid

LONG_MM = np.r_[np.arange(-20.0, -10.5, 1.0), np.arange(11.0, 20.5, 1.0)]
PROFILE_MM = np.arange(-10.0, 10.5, 1.0)
COARSE_MM = np.arange(-10.0, 10.5, 2.0)
CSF_LABELS = (4, 43, 24)


def profile(volume: Any, like: Any, xyz: np.ndarray, normals: np.ndarray, mm: np.ndarray) -> Any:
    t = mm / 1000.0
    pts = (xyz[:, None, :] + t[None, :, None] * normals[:, None, :]).reshape(-1, 3)
    return _sample(volume, like, pts).reshape(len(xyz), len(t))


def ring_curvature(xyz: np.ndarray, faces: np.ndarray, normals: np.ndarray, rings: int) -> Any:
    n = len(xyz)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])
    deg = np.bincount(edges[:, 0], minlength=n).astype(float)
    avg = xyz.copy()
    for _ in range(rings):
        avg = (
            np.stack(
                [
                    np.bincount(edges[:, 0], weights=avg[edges[:, 1], k], minlength=n)
                    for k in range(3)
                ],
                axis=1,
            )
            / np.maximum(deg, 1)[:, None]
        )
    # Positive where the surface bulges outward (vertex outside its neighbourhood mean), in mm.
    return np.sum((xyz - avg) * normals, axis=1) * 1000.0


def extract(case: str) -> None:
    out = ROOT / "cases" / case / "refine-features2.npz"
    if out.exists():
        return
    if not (ROOT / "cases" / case / "refine-features.npz").exists():
        raise SystemExit(f"{case}: run scripts.dev_m33_crop prepare first")
    t1 = load_nifti(ROOT / "mri" / case / "mr.nii.gz")
    synth, _ = to_native_grid(load_synthseg(ROOT / "synthseg" / case / "synthseg.nii.gz"), t1)
    meshes = {
        b: offset_mesh(m, OFFSETS_MM[b]) for b, m in load_watershed(SUBJECTS / case, case).items()
    }
    inner = meshes["inner_skull"]
    xyz, faces = inner.vertices.xyz, np.asarray(inner.faces)
    normals = outward_normals(inner)
    data = t1.array(np.float32)
    labels = synth.array()
    wm = t1_scale(t1, synth)
    csf_mask = np.isin(labels, CSF_LABELS)
    csf = float(np.median(data[csf_mask])) if csf_mask.any() else 0.0
    span = wm - csf if abs(wm - csf) > 1e-6 else wm
    spacing = t1.spacing_m * 1000
    tissue = signed_distance_mm((labels > 0) & (labels != 24), spacing).astype(np.float32)
    extracsf = signed_distance_mm(labels == 24, spacing).astype(np.float32)
    superior = xyz[:, 2] - xyz[:, 2].mean()
    trees = {b: cKDTree(meshes[b].vertices.xyz) for b in ("outer_skull", "outer_scalp")}
    x2 = np.hstack(
        [
            profile(data, t1, xyz, normals, LONG_MM) / wm,
            (profile(data, t1, xyz, normals, PROFILE_MM) - csf) / span,
            profile(tissue, t1, xyz, normals, COARSE_MM),
            profile(extracsf, t1, xyz, normals, COARSE_MM),
            ring_curvature(xyz, faces, normals, 1)[:, None],
            ring_curvature(xyz, faces, normals, 3)[:, None],
            trees["outer_skull"].query(xyz)[0][:, None] * 1000.0,
            trees["outer_scalp"].query(xyz)[0][:, None] * 1000.0,
            superior[:, None] * 1000.0,
        ]
    ).astype(np.float32)
    np.savez_compressed(out, x2=x2, faces=faces.astype(np.int32))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", required=True)
    args = parser.parse_args()
    for case in args.cases:
        extract(case)
        print("done", case, flush=True)


if __name__ == "__main__":
    main()
