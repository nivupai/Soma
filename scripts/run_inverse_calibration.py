"""Execute sealed M31 study from public physical fields and fresh off-grid FEM truth."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from soma.experiments.nonspherical import known_truth
from soma.geometry import Frame, Points
from soma.source.bem_discrepancy import sensors
from soma.source.mesh_replication import candidate_grid
from soma.source.noise import NoiseModel, average_projector
from soma.source.nonspherical import native_forward, pose, source_grid
from soma.source.prior_calibration import PriorInverse, SourcePrior, cell_volumes, source_split
from soma.source.uncertainty import kernels

DESIGN_SHA = "abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc"


def design():
    p = Path("experiments/milestone31/design.json")
    if hashlib.sha256(p.read_bytes()).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen M31 protocol modified")
    return json.loads(p.read_text())


def grids():
    out = {"legacy12": source_grid().xyz[np.r_[0:6, 24:30]]}
    acc = np.empty((0, 3))
    for i, s in enumerate([30, 20, 15]):
        out[f"cart{s}"] = candidate_grid(s).xyz
        acc = np.unique(np.round(np.vstack([acc, out[f"cart{s}"]]), 12), axis=0)
        out[f"nested{i}"] = acc
    return out


def lead_for(head, name, solver, grid):
    root = Path("experiments/milestone30")
    if name.startswith("nested"):
        stage = int(name[-1])
        ps = []
        gs = []
        for spacing in [30, 20, 15][: stage + 1]:
            ps.extend(np.round(candidate_grid(spacing).xyz, 12))
            gs.extend(
                np.loadtxt(root / f"grid-{head}-{spacing}-{solver}-V_per_Am.csv", delimiter=",")
                .reshape(32, -1, 3)
                .transpose(1, 0, 2)
            )
        mapping = {tuple(p): g for p, g in zip(ps, gs, strict=True)}
        return np.stack([mapping[tuple(p)] for p in grid], axis=1).reshape(32, -1)
    spacing = 0 if name == "legacy12" else int(name[4:])
    return np.loadtxt(root / f"grid-{head}-{spacing}-{solver}-V_per_Am.csv", delimiter=",")


def truth(head):
    old, moment = known_truth(head)
    rng = np.random.default_rng(310420 + head)
    xyz = rng.normal(size=(4, 3))
    xyz[:, 2] = abs(xyz[:, 2])
    xyz /= np.linalg.norm(xyz, axis=1)[:, None]
    xyz *= rng.uniform(0.035, 0.060, (4, 1))
    mm = rng.normal(size=(4, 3))
    mm *= 1e-8 / np.linalg.norm(mm, axis=1)[:, None]
    return np.vstack([old.xyz, xyz]), np.vstack([moment, mm])


def new_truth_field(head, xyz, local):
    """Fresh finest native FEM truth; no inverse candidate matrix is reused."""
    from soma.source.fem_reference import full_subtraction
    from soma.source.mesh_replication import boundaries, gmsh_mesh

    target = local / f"truth-{head}"
    target.mkdir(exist_ok=True)
    if (target / "lead.csv").exists():
        request = json.loads((target / "request.json").read_text())
        if request != dict(head=head, sources_m=xyz.tolist(), design_sha256=DESIGN_SHA):
            raise ValueError("Unapproved truth cache identity")
        return np.loadtxt(target / "lead.csv", delimiter=",")
    v, t, labels, q = gmsh_mesh(
        boundaries(head, 3),
        sensors(head),
        json.loads(Path("src/soma/resources/mesh-grid-v30.json").read_text())["max_size_m"][2],
    )
    g, d = full_subtraction(v, t, labels, xyz, sensors(head), [0.33, 1, 0.004, 0.33], quadrature=8)
    if d["relative_residual"] >= 1e-10:
        raise ValueError("Truth solver residual failed")
    np.savetxt(target / "lead.csv", g, delimiter=",")
    (target / "request.json").write_text(
        json.dumps(dict(head=head, sources_m=xyz.tolist(), design_sha256=DESIGN_SHA))
    )
    (target / "diagnostics.json").write_text(json.dumps(dict(mesh=q, solver=d), indent=2) + "\n")
    return g


def run(out, local, only_head=None):
    c = design()
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    gs = grids()
    volumes = {n: cell_volumes(p) for n, p in gs.items()}
    for name, p in gs.items():
        pd.DataFrame(
            dict(x_m=p[:, 0], y_m=p[:, 1], z_m=p[:, 2], cell_volume_m3=volumes[name])
        ).to_csv(out / f"grid-{name}.csv", index=False)
    source_split(c["source_design"]["calibration_ids"], c["source_design"]["test_ids"], 16)
    historical = json.loads(Path("experiments/milestone30/manifest.json").read_text())
    if any(
        hashlib.sha256((Path("experiments/milestone30") / p).read_bytes()).hexdigest() != h
        for p, h in historical.items()
    ):
        raise ValueError("Historical M30 artifact drift")
    rows = []
    operators = []
    curves = []
    replications = []
    physical = []
    failures = []
    examples = []
    psfs = []
    for head in range(6) if only_head is None else [only_head]:
        xyz, mom = truth(head)
        if any(np.min(np.linalg.norm(p[:, None] - xyz[None], axis=2)) < 1e-6 for p in gs.values()):
            raise ValueError("Off-grid generator entered candidate set")
        oldfine = np.loadtxt(f"experiments/milestone30/F-{head}-3-0-V_per_Am.csv", delimiter=",")
        scale = float(np.linalg.norm(oldfine[:, :36], 2))
        newg = new_truth_field(head, xyz[12:], local)
        np.savetxt(out / f"truth-new-{head}-V_per_Am.csv", newg, delimiter=",")
        fine = np.concatenate([oldfine[:, 36:], newg], axis=1)
        clean = np.einsum("ijk,jk->ij", fine.reshape(32, 16, 3), mom)
        for i in range(16):
            physical.append(
                dict(
                    head=head,
                    source=i,
                    split="calibration" if i < 6 else "test",
                    new_heldout=i >= 12,
                    xyz_m=xyz[i].tolist(),
                    moment_Am=mom[i].tolist(),
                )
            )
        p = average_projector(32)
        noise = NoiseModel((5e-8) ** 2 * p, tuple(f"E{i:02}" for i in range(32)), p)
        rng = np.random.default_rng(310421 + head)
        ys = {
            std: [clean + std * p @ rng.normal(size=clean.shape) for _ in range(2)]
            for std in [0.0, 5e-8, 1.5e-7]
        }
        for std, yy in ys.items():
            for draw, y in enumerate(yy):
                np.savetxt(out / f"measurements-{head}-{std}-{draw}-V.csv", y, delimiter=",")
        # Exact original M30 random stream, eight noisy repeats, original 72 sources.
        rngold = np.random.default_rng(37042 + head)
        oldys = []
        oldids = []
        for src in range(12):
            for std in [0.0, 5e-8, 1.5e-7]:
                for draw in range(1 if std == 0 else 8):
                    oldys.append(clean[:, src] + std * p @ rngold.normal(size=32))
                    oldids.append((src, std, draw))
        oldy = np.column_stack(oldys)
        for name, grid in gs.items():
            distance = np.linalg.norm(grid[:, None] - xyz[None], axis=2) * 1000
            nearest = distance.min(axis=0)
            solverlist = ["fem"] + (
                ["openmeeg"] if head in [0, 5] and name in ["cart20", "nested2"] else []
            )
            for solver in solverlist:
                try:
                    g = lead_for(head, name, solver, grid)
                except (ValueError, OSError) as exc:
                    failures.append(
                        dict(
                            head=head,
                            grid=name,
                            solver=solver,
                            stage="forward",
                            error=type(exc).__name__,
                        )
                    )
                    continue
                if name in c["grids"]["original"] and solver == "fem":
                    # Check the new formula against the unchanged MNE/SVD implementation.
                    oldops, _ = kernels(
                        native_forward(g, Points(grid, Frame.MRI), sensors(head), pose({})), scale
                    )
                    for method, oldk in oldops.items():
                        inv = PriorInverse(
                            g,
                            grid,
                            SourcePrior.create(grid, "unweighted", volumes[name]),
                            noise,
                            method,
                        )
                        alpha = inv.alpha(
                            "historical",
                            scale,
                            np.array(c["regularization"]["sweep_log10"]),
                            oldy[:, :6],
                            oldy[:, :6],
                        )[0]
                        k = inv.kernel(alpha)
                        diff = float(np.linalg.norm(k - oldk) / np.linalg.norm(oldk))
                        if diff > 1e-9:
                            raise ValueError(
                                f"Independent historical kernel mismatch {method}: {diff}"
                            )
                        est = k @ oldy
                        peaks = np.linalg.norm(est.reshape(len(grid), 3, -1), axis=1).argmax(axis=0)
                        for j, (src, std, draw) in enumerate(oldids):
                            replications.append(
                                dict(
                                    head=head,
                                    grid=name,
                                    candidates=len(grid),
                                    method=method,
                                    source=src,
                                    noise_std_V=std,
                                    draw=draw,
                                    nearest_mm=float(nearest[src]),
                                    localization_mm=float(distance[peaks[j], src]),
                                    kernel_relative=diff,
                                )
                            )
                for kind in c["priors"]:
                    pr = SourcePrior.create(grid, kind, volumes[name])
                    for method in c["methods"]:
                        inv = PriorInverse(g, grid, pr, noise, method)
                        for std, yy in ys.items():
                            sweep = np.array(c["regularization"]["sweep_log10"])
                            for policy in c["regularization"]["policies"]:
                                stamp = dict(
                                    head=head,
                                    grid=name,
                                    candidates=len(grid),
                                    solver=solver,
                                    prior=kind,
                                    method=method,
                                    noise_std_V=std,
                                    policy=policy,
                                )
                                tick = time.perf_counter()
                                try:
                                    alpha, boundary, losses = inv.alpha(
                                        policy, scale, sweep, yy[0][:, :6], yy[1][:, :6]
                                    )
                                    k = inv.kernel(alpha)
                                    km = inv.kernel(alpha, physical=True)
                                    diag = inv.diagnostics(alpha)
                                    if losses:
                                        base = inv.alpha(
                                            "historical", scale, sweep, yy[0][:, :6], yy[1][:, :6]
                                        )[0]
                                        for multiplier, loss in zip(sweep, losses, strict=True):
                                            curves.append(
                                                dict(
                                                    **stamp,
                                                    alpha=base * 10**multiplier,
                                                    calibration_repeat_MSE=loss,
                                                )
                                            )
                                    resolution_diagonal = np.sum(km * g.T, axis=1)
                                    op = dict(
                                        **stamp,
                                        **diag,
                                        seconds=time.perf_counter() - tick,
                                        boundary_optimum=boundary,
                                        resolution_trace=float(resolution_diagonal.sum()),
                                        resolution_diagonal_mean=float(resolution_diagonal.mean()),
                                        resolution_diagonal_min=float(resolution_diagonal.min()),
                                        resolution_diagonal_max=float(resolution_diagonal.max()),
                                        peak_RSS_MiB=resource.getrusage(
                                            resource.RUSAGE_SELF
                                        ).ru_maxrss
                                        / (1024**2 if sys.platform == "darwin" else 1024),
                                        status="computed",
                                    )
                                    probe = int(np.argmin(distance[:, 12]))
                                    response = np.linalg.norm(
                                        (k @ g[:, 3 * probe : 3 * probe + 3]).reshape(-1, 3, 3),
                                        axis=(1, 2),
                                    )
                                    energy = response**2
                                    op["PSF_RMS_width_mm"] = float(
                                        np.sqrt(
                                            energy
                                            @ np.sum((grid - grid[probe]) ** 2, axis=1)
                                            / energy.sum()
                                        )
                                        * 1000
                                    )
                                    operators.append(op)
                                    if (
                                        head == 0
                                        and solver == "fem"
                                        and std == 5e-8
                                        and policy == "spectral"
                                    ):
                                        for i, value in enumerate(response):
                                            psfs.append(
                                                dict(
                                                    **stamp,
                                                    candidate=i,
                                                    x_m=grid[i, 0],
                                                    y_m=grid[i, 1],
                                                    z_m=grid[i, 2],
                                                    response=value,
                                                    probe=probe,
                                                    units="1/(A*m)" if method == "dSPM" else "1",
                                                )
                                            )
                                    for draw, y in enumerate(yy[:1] if std == 0 else yy):
                                        estimate = (k @ y).reshape(len(grid), 3, 16)
                                        amplitude = np.linalg.norm(estimate, axis=1)
                                        energies = amplitude**2
                                        peak = amplitude.argmax(axis=0)
                                        prediction = g @ km @ y
                                        residual = noise.whitener @ (prediction - y)
                                        for src in range(16):
                                            err = float(distance[peak[src], src])
                                            dispersion = float(
                                                np.sqrt(
                                                    energies[:, src]
                                                    @ distance[:, src] ** 2
                                                    / energies[:, src].sum()
                                                )
                                            )
                                            rows.append(
                                                dict(
                                                    **stamp,
                                                    source=src,
                                                    split="calibration" if src < 6 else "test",
                                                    new_heldout=src >= 12,
                                                    draw=draw,
                                                    localization_mm=err,
                                                    nearest_mm=nearest[src],
                                                    excess_mm=err - nearest[src],
                                                    dispersion_mm=dispersion,
                                                    depth_radius_mm=np.linalg.norm(xyz[src]) * 1000,
                                                    orientation_radial_cosine=abs(
                                                        float(
                                                            mom[src]
                                                            @ xyz[src]
                                                            / np.linalg.norm(mom[src])
                                                            / np.linalg.norm(xyz[src])
                                                        )
                                                    ),
                                                    whitened_residual=float(
                                                        np.linalg.norm(residual[:, src])
                                                    ),
                                                    sensor_clean_MSE=float(
                                                        np.mean(
                                                            (prediction[:, src] - clean[:, src])
                                                            ** 2
                                                        )
                                                    ),
                                                    physical_peak_Am=None
                                                    if method == "dSPM"
                                                    else float(amplitude[peak[src], src]),
                                                    status="computed",
                                                )
                                            )
                                        if (
                                            head == 0
                                            and name == "nested2"
                                            and solver == "fem"
                                            and std == 5e-8
                                            and draw == 0
                                            and policy == "spectral"
                                        ):
                                            examples.append(
                                                dict(
                                                    **stamp,
                                                    source=12,
                                                    grid_mm=(grid * 1000).tolist(),
                                                    truth_mm=(xyz[12] * 1000).tolist(),
                                                    amplitude=amplitude[:, 12].tolist(),
                                                    PSF=response.tolist(),
                                                    units="dimensionless"
                                                    if method == "dSPM"
                                                    else "A*m",
                                                )
                                            )
                                except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
                                    failures.append(
                                        dict(
                                            **stamp,
                                            stage="inverse",
                                            error=type(exc).__name__,
                                            reason=str(exc),
                                        )
                                    )
            print("head", head, name, "complete", flush=True)
            if time.perf_counter() - started > c["budget"]["total_seconds"]:
                raise TimeoutError("Frozen M31 total budget")
        for name, data in [
            ("reconstructions", rows),
            ("operators", operators),
            ("regularization-curves", curves),
            ("M30-replication", replications),
            ("point-spread", psfs),
        ]:
            pd.DataFrame(data).to_csv(out / (name + ".csv"), index=False)
        for name, data in [("sources", physical), ("failures", failures), ("examples", examples)]:
            (out / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n")
    receipt = dict(
        schema="soma.inverse-calibration.receipt/1",
        design_sha256=DESIGN_SHA,
        heads=6 if only_head is None else 1,
        original_sources=72 if only_head is None else 12,
        new_heldout_sources=24 if only_head is None else 4,
        reconstruction_rows=len(rows),
        operator_rows=len(operators),
        failed_configurations=len(failures),
        seconds=time.perf_counter() - started,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        synthetic_only=True,
        external_preregistration=False,
    )
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--local", type=Path, required=True)
    p.add_argument("--head", type=int)
    a = p.parse_args()
    run(a.output, a.local, a.head)
