"""M33 inner skull: a small 3D U-Net trained on CT-derived labels (development pools only).

The network reads the cropped T1 and SynthSeg's intracranial distance map on a 2 mm grid and
predicts, for every voxel, the signed distance (mm, + outside) to the CT inner skull. Each
calibrated watershed inner-skull vertex is then moved by the predicted distance sampled at the
vertex, smoothed over the mesh and clipped, exactly like the gradient-boosted refinement, so the
same mesh scoring applies. Training is leave-one-centre-out over the 180 SynthRAD2023 cases (a
model per held-out centre). CT is used only for training targets and scoring; nothing here
touches CERMEP.

    python -m scripts.dev_m33_skull_net install-check
    python -m scripts.dev_m33_skull_net prepare --case 1BA001
    python -m scripts.dev_m33_skull_net train --fold A
    python -m scripts.dev_m33_skull_net score --case 1BA001
    python -m scripts.dev_m33_skull_net aggregate
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

NET = Path("reports/milestone33/skull-net")
GRID_MM = 2.0
MULTIPLE = 16
TARGET_CLIP_MM = 20.0
CENTRES = "ABC"
SEED = 11042
ITERATIONS = 6000
NAME = "net-metrics.json"
HYBRID = "hybrid-metrics.json"


# ---------------------------------------------------------------- data on a common 2 mm grid
def grid_for(t1: Any) -> tuple[np.ndarray, tuple[int, int, int]]:
    """Axis-aligned RAS grid (metres) covering the cropped T1, sides a multiple of 16 voxels."""
    shape = np.array(t1.shape)
    corners = np.array(
        [[i, j, k, 1.0] for i in (0, shape[0] - 1) for j in (0, shape[1] - 1) for k in (0, shape[2] - 1)]
    )
    world = (corners @ np.asarray(t1.affine_m).T)[:, :3]
    lo, hi = world.min(axis=0), world.max(axis=0)
    step = GRID_MM / 1000.0
    n = np.ceil((hi - lo) / step).astype(int) + 1
    n = ((n + MULTIPLE - 1) // MULTIPLE) * MULTIPLE
    centre = (lo + hi) / 2
    origin = centre - step * (n - 1) / 2
    affine = np.eye(4)
    affine[:3, :3] *= step
    affine[:3, 3] = origin
    return affine, (int(n[0]), int(n[1]), int(n[2]))


def grid_points(affine: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    idx = np.stack(np.meshgrid(*[np.arange(s) for s in shape], indexing="ij"), -1).reshape(-1, 3)
    return idx @ affine[:3, :3].T + affine[:3, 3]


def sample_grid(grid_data: np.ndarray, affine: np.ndarray, xyz_m: np.ndarray) -> np.ndarray:
    vox = np.linalg.solve(affine[:3, :3], (xyz_m - affine[:3, 3]).T)
    return np.asarray(ndimage.map_coordinates(grid_data, vox, order=1, mode="nearest"))


def prepare(case: str) -> None:
    from scripts.dev_m33_crop import ROOT
    from scripts.dev_m33_skull import DATA
    from soma.anatomy.inner_skull_refine import _sample, signed_distance_mm, t1_scale
    from soma.benchmarks.ct_skull import CTSkullParameters, ct_truth
    from soma.imaging.nifti import load_nifti
    from soma.pipeline.synthseg import load_synthseg, to_native_grid

    out = NET / "cases" / case / "grid.npz"
    if out.exists():
        return
    t1 = load_nifti(ROOT / "mri" / case / "mr.nii.gz")
    synth, _ = to_native_grid(load_synthseg(ROOT / "synthseg" / case / "synthseg.nii.gz"), t1)
    affine, shape = grid_for(t1)
    pts = grid_points(affine, shape)
    scale = t1_scale(t1, synth)
    image = _sample(t1.array(np.float32), t1, pts).reshape(shape) / scale
    inside_t1 = _inside(t1, pts).reshape(shape)
    image[~inside_t1] = 0.0
    icv = signed_distance_mm(synth.array() > 0, t1.spacing_m * 1000).astype(np.float32)
    icv_grid = _sample(icv, t1, pts).reshape(shape)
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    cavity = ct_truth(ct, mask, parameters=CTSkullParameters()).masks["inner_skull"]
    sd = signed_distance_mm(cavity.array().astype(bool), cavity.spacing_m * 1000).astype(np.float32)
    target = _sample(sd, cavity, pts).reshape(shape)
    valid = _inside(cavity, pts).reshape(shape) & inside_t1
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        image=image.astype(np.float16),
        icv=np.clip(icv_grid, -TARGET_CLIP_MM, TARGET_CLIP_MM).astype(np.float16),
        target=np.clip(target, -TARGET_CLIP_MM, TARGET_CLIP_MM).astype(np.float16),
        valid=valid,
        affine=affine,
    )


def _inside(volume: Any, pts: np.ndarray) -> np.ndarray:
    from soma.geometry import Frame, Points

    vox = volume.grid.to_voxel(Points(pts, Frame.RAS))
    return np.all((vox >= -0.5) & (vox <= np.array(volume.shape) - 0.5), axis=1)


# ---------------------------------------------------------------- network
def build_unet(base: int = 16) -> Any:
    import torch
    from torch import nn

    def block(cin: int, cout: int) -> nn.Module:
        return nn.Sequential(
            nn.Conv3d(cin, cout, 3, padding=1),
            nn.InstanceNorm3d(cout, affine=True),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Conv3d(cout, cout, 3, padding=1),
            nn.InstanceNorm3d(cout, affine=True),
            nn.LeakyReLU(0.1, inplace=True),
        )

    class UNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            c = [base, base * 2, base * 4, base * 8]
            self.enc = nn.ModuleList([block(2, c[0]), block(c[0], c[1]), block(c[1], c[2])])
            self.mid = block(c[2], c[3])
            self.up = nn.ModuleList(
                [nn.ConvTranspose3d(c[i + 1], c[i], 2, stride=2) for i in (2, 1, 0)]
            )
            self.dec = nn.ModuleList([block(c[i] * 2, c[i]) for i in (2, 1, 0)])
            self.head = nn.Conv3d(c[0], 1, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            skips = []
            for enc in self.enc:
                x = enc(x)
                skips.append(x)
                x = nn.functional.max_pool3d(x, 2)
            x = self.mid(x)
            for up, dec, skip in zip(self.up, self.dec, reversed(skips), strict=True):
                x = dec(torch.cat([up(x), skip], dim=1))
            # Predict a residual on top of SynthSeg's intracranial distance (channel 1, /10 mm).
            return self.head(x)

    return UNet()


def device() -> Any:
    import torch

    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def pool() -> list[str]:
    from scripts.dev_m33_crop import SPLIT_FILE

    split = json.loads(SPLIT_FILE.read_text())
    return sorted(split["development"] + split["held_out"])


def load_grid(case: str) -> dict[str, np.ndarray]:
    d = np.load(NET / "cases" / case / "grid.npz")
    return {k: d[k] for k in d.files}


def tensors(g: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.stack([g["image"].astype(np.float32), g["icv"].astype(np.float32) / 10.0])
    y = g["target"].astype(np.float32)[None] / 10.0
    # Weight voxels near the CT inner skull most; ignore voxels outside either scan.
    w = (1.0 + 4.0 * np.exp(-np.abs(g["target"].astype(np.float32)) / 5.0)) * g["valid"]
    return x, y, w[None].astype(np.float32)


def augment(x: np.ndarray, y: np.ndarray, w: np.ndarray, rng: Any) -> tuple[Any, Any, Any]:
    if rng.random() < 0.5:  # left-right flip (grid axis 0 is world x)
        x, y, w = x[:, ::-1], y[:, ::-1], w[:, ::-1]
    gamma = float(np.exp(rng.uniform(np.log(0.75), np.log(1.33))))
    x = x.copy()
    x[0] = np.clip(x[0], 0, None) ** gamma * rng.uniform(0.9, 1.1)
    x[0] += rng.normal(0, 0.02, size=x[0].shape).astype(np.float32)
    shift = rng.integers(-4, 5, size=3)
    x, y, w = (np.roll(a, tuple(shift), axis=(1, 2, 3)) for a in (x, y, w))
    return np.ascontiguousarray(x), np.ascontiguousarray(y), np.ascontiguousarray(w)


def model_path(fold: str) -> Path:
    return NET / "models" / f"unet-fold-{fold}.pt"


def train(fold: str) -> None:
    import torch

    path = model_path(fold)
    if path.exists():
        return
    with gpu_lock():
        _train(fold, path)


class gpu_lock:
    """One training run at a time on the Mac GPU, even when the queue runs two tasks."""

    path = NET / "models" / "train.lock"

    def __enter__(self) -> None:
        import os

        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return
            except FileExistsError:
                try:
                    os.kill(int(self.path.read_text() or "0"), 0)
                except (ProcessLookupError, ValueError):
                    self.path.unlink(missing_ok=True)  # stale lock from a killed run
                    continue
                except PermissionError:
                    pass
                time.sleep(30)

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


def _train(fold: str, path: Path) -> None:
    import torch

    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED + ord(fold))
    cases = [c for c in pool() if c[2] != fold and (NET / "cases" / c / "grid.npz").exists()]
    data = [tensors(load_grid(c)) for c in cases]
    dev = device()
    net = build_unet().to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=ITERATIONS)
    log_path = NET / "models" / f"unet-fold-{fold}.log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    start, running = time.time(), []
    for it in range(1, ITERATIONS + 1):
        x, y, w = augment(*data[int(rng.integers(len(data)))], rng)
        xt, yt, wt = (torch.from_numpy(a)[None].to(dev) for a in (x, y, w))
        pred = net(xt) + xt[:, 1:2]  # residual on SynthSeg's intracranial distance
        loss = (torch.abs(pred - yt) * wt).sum() / wt.sum().clamp_min(1.0)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        running.append(float(loss.detach()) * 10.0)  # mm
        if it % 100 == 0:
            entry = {
                "iteration": it,
                "of": ITERATIONS,
                "weighted_l1_mm": float(np.mean(running)),
                "minutes": round((time.time() - start) / 60, 1),
            }
            running = []
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            print(json.dumps(entry), flush=True)
    torch.save({"state": net.state_dict(), "cases": cases, "iterations": ITERATIONS}, path)


def predict_grid(case: str) -> tuple[np.ndarray, np.ndarray]:
    import torch

    g = load_grid(case)
    x, _, _ = tensors(g)
    dev = device()
    net = build_unet().to(dev)
    net.load_state_dict(torch.load(model_path(case[2]), map_location=dev)["state"])
    net.eval()
    with torch.no_grad():
        xt = torch.from_numpy(x)[None].to(dev)
        flipped = torch.flip(xt, dims=[2])
        a = net(xt) + xt[:, 1:2]
        b = torch.flip(net(flipped) + flipped[:, 1:2], dims=[2])  # test-time flip average
        pred = ((a + b) / 2)[0, 0].cpu().numpy() * 10.0
    return pred, g["affine"]


# ---------------------------------------------------------------- scoring with the mesh pipeline
def score(case: str) -> None:
    from scripts.dev_m33_crop import ROOT, prepared
    from scripts.dev_m33_skull import DATA, fs_env
    from soma.anatomy.fs_skull import voxelize
    from soma.anatomy.inner_skull_refine import RefineParameters, apply_correction
    from soma.anatomy.t1_skull import mask_volume, pad
    from soma.benchmarks.ct_skull import CTSkullParameters, RegionRule, ct_truth, score_case
    from soma.core.provenance import write_json
    from soma.imaging.nifti import load_nifti

    out_net = ROOT / "cases" / case / NAME
    out_hybrid = ROOT / "cases" / case / HYBRID
    if out_net.exists() and out_hybrid.exists():
        return
    params = RefineParameters(smoothing_iterations=5, max_correction_mm=12.0)
    pred, affine = predict_grid(case)
    _, _, (meshes,) = prepared(case, fs_env())
    inner = meshes["inner_skull"]
    net_pred = sample_grid(pred, affine, inner.vertices.xyz)
    full = load_nifti(DATA / case / "mr.nii.gz")
    ct = load_nifti(DATA / case / "ct.nii.gz")
    mask = load_nifti(DATA / case / "mask.nii.gz", kind="labels")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    like = pad(full, CTSkullParameters().padding_voxels)

    def run(correction: np.ndarray, out: Path) -> None:
        m = dict(meshes)
        m["inner_skull"] = apply_correction(inner, correction, params)
        masks = {b: mask_volume(voxelize(v, like), like, boundary=b) for b, v in m.items()}
        write_json(out, {"case": case, "scores": score_case(m, masks, truth, region)})

    run(net_pred, out_net)
    # Hybrid: average the network with the gradient-boosted "ideas" model (same fold).
    from scripts.dev_m33_skull_score_ideas import predict as ideas_predict

    run(0.5 * (net_pred + ideas_predict(case)), out_hybrid)


def aggregate() -> None:
    from scripts.dev_m33_crop import ROOT

    names = {
        "v32": "refined180-metrics.json",
        "ideas": "ideas-metrics.json",
        "net": NAME,
        "hybrid": HYBRID,
    }
    rows: dict[str, dict[str, tuple[float, float]]] = {}
    for case in pool():
        files = {k: ROOT / "cases" / case / v for k, v in names.items()}
        if not all(f.exists() for f in files.values()):
            continue
        rows[case] = {}
        for k, f in files.items():
            b = json.loads(f.read_text())["scores"]["boundaries"]["inner_skull"]
            rows[case][k] = (b["mean_abs_mm"], b["HD95_mm"])
    rng = np.random.default_rng(SEED)
    summary: dict[str, Any] = {
        "boundary": "inner_skull",
        "scheme": "leave-one-centre-out, 180 SynthRAD2023 cases, development only",
        "models": {
            "v32": "gradient-boosted refinement, 180-case retrain",
            "ideas": "gradient-boosted, extra features + second pass + smoothing 5 / clip 12",
            "net": "3D U-Net distance map, smoothing 5 / clip 12",
            "hybrid": "average of net and ideas corrections",
        },
    }
    for group in ("all", *CENTRES):
        keys = [c for c in rows if group == "all" or c[2] == group]
        if not keys:
            continue
        entry: dict[str, Any] = {"cases": len(keys)}
        for k in names:
            mad = np.array([rows[c][k][0] for c in keys])
            hd = np.array([rows[c][k][1] for c in keys])
            entry[k] = {
                "mean_abs_mm": float(mad.mean()),
                "mean_abs_mm_median": float(np.median(mad)),
                "HD95_mm": float(hd.mean()),
            }
            if k != "v32":
                diff = mad - np.array([rows[c]["v32"][0] for c in keys])
                boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)]
                entry[k]["change_vs_v32_mm"] = float(diff.mean())
                entry[k]["change_vs_v32_95ci_mm"] = [
                    float(np.percentile(boots, 2.5)),
                    float(np.percentile(boots, 97.5)),
                ]
                entry[k]["cases_improved_vs_v32"] = int((diff < 0).sum())
        summary[group] = entry
    path = NET / "summary.json"
    path.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def install_check() -> None:
    import torch

    dev = device()
    x = torch.randn(1, 2, 32, 32, 32, device=dev)
    y = build_unet().to(dev)(x)
    assert y.shape == (1, 1, 32, 32, 32)
    NET.mkdir(parents=True, exist_ok=True)
    (NET / "torch-ok.json").write_text(
        json.dumps({"torch": torch.__version__, "device": str(dev)}) + "\n"
    )
    print("torch", torch.__version__, "device", dev)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["install-check", "prepare", "train", "score", "aggregate"])
    parser.add_argument("--case")
    parser.add_argument("--fold", choices=list(CENTRES))
    args = parser.parse_args()
    if args.step == "install-check":
        install_check()
    elif args.step == "prepare":
        if args.case not in pool():
            raise SystemExit("Development pool only")
        prepare(args.case)
        print("done", args.case, flush=True)
    elif args.step == "train":
        train(args.fold)
    elif args.step == "score":
        if args.case not in pool():
            raise SystemExit("Development pool only")
        score(args.case)
        print("done", args.case, flush=True)
    else:
        aggregate()


if __name__ == "__main__":
    main()
