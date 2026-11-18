"""Frozen mesh replication and paired source-grid experiment; synthetic inputs only."""

import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.experiments.nonspherical import known_truth
from soma.experiments.source_uncertainty import source_metrics
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import _point_triangle
from soma.protocol.model import SealedProtocol
from soma.results.contracts import canonical
from soma.source.bem_discrepancy import (
    contract_hashes,
    field_metrics,
    homogeneous_series,
    sensors,
    solve,
)
from soma.source.fem_reference import layered_sphere_series
from soma.source.mesh_replication import boundaries, candidate_grid, nearest_distances
from soma.source.noise import average_projector
from soma.source.nonspherical import native_forward, pose, source_grid
from soma.source.uncertainty import kernels


def design() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("mesh-grid-v30.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "19d681211937bdba3b55c54eade56920d98593dcb365ab0047eda75411c5e3a9"
    ):
        raise ValueError("Frozen mesh/grid design drift")
    return dict(json.loads(raw))


def protocol() -> SealedProtocol:
    s = SealedProtocol(files("soma.resources").joinpath("mesh-grid-protocol-v30.json").read_bytes())
    if s.protocol.fingerprint != "61360de2076b3e4e01853358b3a66bcf69aced771fb7ad7e11f4b1cfff8cc46b":
        raise ValueError("Frozen mesh/grid seal drift")
    return s


def run(output: Path, parent: Path = Path("experiments/milestone29")) -> dict[str, Any]:
    c = design()
    sealed = protocol()
    output.mkdir(parents=True, exist_ok=False)
    (output / "protocol.json").write_bytes(canonical(sealed.record()))
    started = time.perf_counter()
    if (
        hashlib.sha256((parent / "manifest.json").read_bytes()).hexdigest()
        != "8efa2f26c959bc5765f0e8a8586332e14d18fd4ede15b113d9a520c1a60ed135"
    ):
        raise ValueError("Unapproved independent parent reference")
    manifest = json.loads((parent / "manifest.json").read_text())
    if any(hashlib.sha256((parent / p).read_bytes()).hexdigest() != h for p, h in manifest.items()):
        raise ValueError("Parent M29 artifact drift")
    fields = {}
    models = []
    comparisons = []
    geometry_rows = []
    meshes_by_key: dict[tuple[int | None, int, bool], Path] = {}
    inverse = []
    resolutions = []
    psfs = []
    peaks = []
    source_rows = []
    legacy = Points(source_grid().xyz[np.r_[0:6, 24:30]], Frame.MRI)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")

    def execute(command: list[str], target: Path) -> None:
        if time.perf_counter() - started > c["budget"]["total_seconds"]:
            raise TimeoutError("Frozen study resource budget")
        with (target / "worker.log").open("w") as log:
            subprocess.run(
                command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240
            )

    def failure(exc: Exception, target: Path) -> str:
        if (target / "worker.log").exists():
            lines = (target / "worker.log").read_text().splitlines()
            for line in reversed(lines):
                if (
                    line.startswith(("ValueError:", "MemoryError:", "RuntimeError:"))
                    and "/Users/" not in line
                ):
                    return line
        return type(exc).__name__ + "; detailed local log retained"

    def mesh(head: int | None, level: int, alt: bool) -> Path:
        key = (head, level, alt)
        if key in meshes_by_key:
            return meshes_by_key[key]
        target = output / f"mesh-{head}-{level}-{int(alt)}"
        target.mkdir()
        bs = boundaries(head, level, alt)
        arrays = {"sensors": sensors(head)}
        for i, b in enumerate(bs):
            arrays.update({f"v{i}": b.vertices.xyz, f"f{i}": b.faces})
        np.savez_compressed(target / "surfaces.npz", **arrays)
        (target / "request.local.json").write_text(
            json.dumps(dict(max_size_m=c["max_size_m"][level - 1]))
        )
        execute([sys.executable, "-m", "soma.source.mesh_worker", str(target)], target)
        meshes_by_key[key] = target
        if alt:
            reference = boundaries(head, 3, False)
            for tissue, (a, b) in enumerate(zip(bs, reference, strict=True)):
                for direction, left, right in [
                    ("alternative-to-std", a, b),
                    ("std-to-alternative", b, a),
                ]:
                    tri = right.vertices.xyz[right.faces]
                    probes = np.vstack(
                        [left.vertices.xyz, left.vertices.xyz[left.faces].mean(axis=1)]
                    )
                    distance = np.array(
                        [
                            _point_triangle(np.broadcast_to(p, (len(tri), 3)), tri).min() * 1000
                            for p in probes
                        ]
                    )
                    geometry_rows.append(
                        dict(
                            head=head,
                            level=level,
                            tissue=tissue,
                            direction=direction,
                            sampled_max_mm=float(distance.max()),
                            sampled_mean_mm=float(distance.mean()),
                            sampling="vertices and facet centroids; not certified Hausdorff",
                        )
                    )
        return target

    def fem(
        head: int | None, level: int, alt: bool, points: Any, sigmas: list[float], label: str
    ) -> tuple[Any, dict[str, Any]]:
        target = mesh(head, level, alt)
        with np.load(target / "mesh.npz", allow_pickle=False) as z:
            v, t, labels = [z[k] for k in ["vertices", "tetrahedra", "labels"]]
        chunks = []
        ds = []
        for first in range(0, len(points), 72):
            part = output / (label + f"-batch{first // 72}")
            part.mkdir()
            np.savez_compressed(
                part / "input.npz",
                vertices=v,
                tetrahedra=t,
                labels=labels,
                sources=points[first : first + 72],
                sensors=sensors(head),
            )
            (part / "request.local.json").write_text(json.dumps(dict(sigmas=sigmas, quadrature=8)))
            execute([sys.executable, "-m", "soma.source.fem_worker", str(part)], part)
            chunks.append(np.loadtxt(part / "lead.csv", delimiter=","))
            ds.append(json.loads((part / "diagnostics.json").read_text()))
        d = json.loads((target / "mesh-audit.json").read_text())
        d.update(
            solve_seconds=sum(x["seconds"] for x in ds),
            peak_solver_MiB=max(x["peak_child_MiB"] for x in ds),
            residual=max(x["relative_residual"] for x in ds),
            current_imbalance=max(x["preprojection_current_imbalance"] for x in ds),
        )
        return np.concatenate(chunks, axis=1), d

    def bem(head: int, points: Any, label: str) -> Any:
        chunks = []
        for first in range(0, len(points), 72):
            chunks.append(
                solve(
                    boundaries(head, 2),
                    points[first : first + 72],
                    sensors(head),
                    c["sigmas_S_m"],
                    output / (label + f"-batch{first // 72}"),
                    solver="openmeeg",
                )[0]
            )
        return np.concatenate(chunks, axis=1)

    def compare(label: str, head: int | None, level: int, a: Any, b: Any, condition: str) -> None:
        m = field_metrics(a, b)
        comparisons.append(dict(label=label, head=head, level=level, condition=condition, **m))
        for i, value in enumerate(m["source_relative"]):
            source_rows.append(
                dict(
                    label=label,
                    head=head,
                    level=level,
                    condition=condition,
                    source=i,
                    relative=value,
                    independent_source=i >= 12,
                )
            )

    # Verify source/sensor/conductivity identities before reusing M29 std fields.
    old_models = json.loads((parent / "models.json").read_text())

    def parent_field(
        label: str, head: int | None, level: int, solver: str, sigmas: list[float]
    ) -> Any:
        truth, _ = known_truth(head or 0)
        pp = np.vstack([legacy.xyz, truth.xyz])
        bs = boundaries(head, level)
        if solver == "openmeeg":
            m = next(
                m
                for m in old_models
                if m["label"] == label and m["solver"] == solver and m["status"] == "computed"
            )
            if m["diagnostics"]["contracts"] != contract_hashes(
                [(b.vertices.xyz, b.faces) for b in bs], pp, sensors(head), sigmas
            ):
                raise ValueError("Parent physical input mismatch")
        g = np.loadtxt(parent / (label + "-" + solver + "-V_per_Am.csv"), delimiter=",")
        if g.shape != (32, 72):
            raise ValueError("Parent operator shape mismatch")
        return g

    for family, sigmas in [("H", [0.33] * 4), ("S", c["sigmas_S_m"])]:
        for level, alt in [(1, False), (2, False), (3, False), (3, True)]:
            label = f"{family}-{level}-{int(alt)}"
            truth, _ = known_truth(0)
            pp = np.vstack([legacy.xyz, truth.xyz])
            row: dict[str, Any] = dict(
                label=label,
                head=None,
                level=level,
                alternative=alt,
                status="FAILED",
                kind="analytical",
            )
            try:
                g, d = fem(None, level, alt, pp, sigmas, label)
                fields[label] = g
                row.update(status="computed", diagnostics=d)
                exact = (
                    average_projector(32) @ homogeneous_series(pp, sensors(None))
                    if family == "H"
                    else layered_sphere_series(pp, sensors(None), c["radii_m"], sigmas)[0]
                )
                compare(label, None, level, g, exact, "analytical " + family)
                om = parent_field(f"{family}-{level}", None, level, "openmeeg", sigmas)
                compare(
                    label + "-vs-BEM",
                    None,
                    level,
                    g,
                    om,
                    "D matched" if not alt else "D distinct boundary",
                )
            except (
                ValueError,
                ArithmeticError,
                subprocess.SubprocessError,
                MemoryError,
                TimeoutError,
            ) as exc:
                row["reason"] = failure(exc, output / (label + "-batch0"))
            models.append(row)
            print(label, row["status"], flush=True)
    for head in c["heads"]:
        truth, _ = known_truth(head)
        pp = np.vstack([legacy.xyz, truth.xyz])
        for level, alt in [(1, False), (2, False), (3, False), (2, True), (3, True)]:
            label = f"F-{head}-{level}-{int(alt)}"
            row = dict(
                label=label,
                head=head,
                level=level,
                alternative=alt,
                status="FAILED",
                kind="forward",
            )
            try:
                g, d = fem(head, level, alt, pp, c["sigmas_S_m"], label)
                fields[label] = g
                row.update(status="computed", diagnostics=d)
                om = parent_field(f"C-{head}-{level}", head, level, "openmeeg", c["sigmas_S_m"])
                radial = parent_field(f"C-{head}-{level}", head, level, "fem", c["sigmas_S_m"])
                compare(
                    label, head, level, g, om, "B matched" if not alt else "C distinct boundary"
                )
                compare(
                    label + "-radial",
                    head,
                    level,
                    g,
                    radial,
                    "A radial/Gmsh" if not alt else "C geometry and volume",
                )
                if alt and level == 3:
                    om_alt, diag = solve(
                        boundaries(head, 3, True),
                        pp,
                        sensors(head),
                        c["sigmas_S_m"],
                        output / (label + "-BEM-alt"),
                        solver="openmeeg",
                    )
                    fields[label + "-BEM-alt"] = om_alt
                    compare(label + "-matched-alt", head, level, g, om_alt, "B alternative matched")
                    compare(label + "-BEM-geometry", head, level, om_alt, om, "C BEM geometry only")
                    row["BEM_alternative_diagnostics"] = diag
            except (
                ValueError,
                ArithmeticError,
                subprocess.SubprocessError,
                MemoryError,
                TimeoutError,
            ) as exc:
                row["reason"] = failure(exc, output / (label + "-batch0"))
            models.append(row)
            print(label, row["status"], flush=True)
        fine = fields.get(f"F-{head}-3-0")
        if fine is None:
            continue
        scale = float(np.linalg.norm(fine[:, :36], 2))
        clean = np.einsum("ijk,jk->ij", fine[:, 36:].reshape(32, 12, 3), known_truth(head)[1])
        rng = np.random.default_rng(37042 + head)
        ids = []
        ys = []
        noise_vectors = []
        for source, std in itertools.product(range(12), [0.0, 5e-8, 1.5e-7]):
            for draw in range(1 if std == 0 else 8):
                noise = std * average_projector(32) @ rng.normal(size=32)
                noise_vectors.append(noise)
                ys.append(clean[:, source] + noise)
                ids.append(dict(source=source, noise_std_V=std, draw=draw))
        y = np.column_stack(ys)
        np.savetxt(output / f"head-{head}-measurements_V.csv", y, delimiter=",")
        for spacing in [0, 30, 20, 15]:
            grid = legacy if spacing == 0 else candidate_grid(spacing)
            nearest = nearest_distances(grid.xyz, truth.xyz)
            for solver in ["fem", "openmeeg"]:
                label = f"grid-{head}-{spacing}-{solver}"
                row = dict(
                    label=label,
                    head=head,
                    spacing_mm=spacing,
                    candidates=len(grid.xyz),
                    solver=solver,
                    status="FAILED",
                    kind="grid",
                )
                try:
                    if spacing == 0:
                        g = (
                            fields[f"F-{head}-2-0"][:, :36]
                            if solver == "fem"
                            else parent_field(f"C-{head}-2", head, 2, "openmeeg", c["sigmas_S_m"])[
                                :, :36
                            ]
                        )
                        d = {}
                    elif solver == "fem":
                        g, d = fem(head, 2, False, grid.xyz, c["sigmas_S_m"], label)
                    else:
                        g = bem(head, grid.xyz, label)
                        d = {}
                    fields[label] = g
                    ops, operator_diag = kernels(
                        native_forward(g, grid, sensors(head), pose({})), scale
                    )
                    row.update(status="computed", diagnostics=d, operator_diagnostics=operator_diag)
                    for method, k in ops.items():
                        estimate = k @ y
                        r = k @ g
                        sv = np.linalg.svd(g, compute_uv=False)
                        local = output / (label + "-" + method + "-resolution.npy")
                        np.save(local, r)
                        resolutions.append(
                            dict(
                                head=head,
                                spacing_mm=spacing,
                                candidates=len(grid.xyz),
                                solver=solver,
                                method=method,
                                resolution_norm=float(np.linalg.norm(r)),
                                resolution_trace=float(np.trace(r)),
                                resolution_sha256=hashlib.sha256(local.read_bytes()).hexdigest(),
                                resolution_units="1/(A*m)" if method == "dSPM" else "1",
                                lead_rank=int(np.sum(sv > sv[0] * 1e-12)),
                                lead_condition_nonnull=float(
                                    sv[0] / sv[np.sum(sv > sv[0] * 1e-12) - 1]
                                ),
                            )
                        )
                        for src in range(3):
                            candidate = int(
                                np.argmin(np.linalg.norm(grid.xyz - truth.xyz[src], axis=1))
                            )
                            block = r[:, candidate * 3 : candidate * 3 + 3].reshape(
                                len(grid.xyz), 3, 3
                            )
                            amplitude = np.linalg.norm(block, axis=(1, 2))
                            for j, value in enumerate(amplitude):
                                psfs.append(
                                    dict(
                                        head=head,
                                        spacing_mm=spacing,
                                        solver=solver,
                                        method=method,
                                        probe=src,
                                        candidate=j,
                                        x_m=grid.xyz[j, 0],
                                        y_m=grid.xyz[j, 1],
                                        z_m=grid.xyz[j, 2],
                                        response_frobenius=value,
                                    )
                                )
                        for col, ident in enumerate(ids):
                            metrics = source_metrics(
                                estimate[:, col], grid, truth, int(ident["source"]), method
                            )
                            inverse.append(
                                dict(
                                    head=head,
                                    spacing_mm=spacing,
                                    candidates=len(grid.xyz),
                                    solver=solver,
                                    method=method,
                                    status="computed",
                                    **ident,
                                    **metrics,
                                    excess_localization_mm=metrics["localization_mm"]
                                    - nearest[int(ident["source"])],
                                )
                            )
                            if ident["noise_std_V"] == 5e-8 and ident["draw"] == 0:
                                peaks.append(
                                    dict(
                                        head=head,
                                        spacing_mm=spacing,
                                        solver=solver,
                                        method=method,
                                        source=int(ident["source"]),
                                        truth_xyz_m=truth.xyz[int(ident["source"])].tolist(),
                                        peak_xyz_m=grid.xyz[int(metrics["peak"])].tolist(),
                                    )
                                )
                    if spacing == 15 and head in [0, 5] and f"F-{head}-3-1" in fields:
                        alternate = np.einsum(
                            "ijk,jk->ij",
                            fields[f"F-{head}-3-1"][:, 36:].reshape(32, 12, 3),
                            known_truth(head)[1],
                        )
                        alt_y = np.column_stack(
                            [
                                alternate[:, int(ident["source"])] + noise
                                for ident, noise in zip(ids, noise_vectors, strict=True)
                            ]
                        )
                        for method, k in ops.items():
                            estimates = k @ alt_y
                            for col, ident in enumerate(ids):
                                if ident["noise_std_V"] != 5e-8:
                                    continue
                                inverse.append(
                                    dict(
                                        head=head,
                                        spacing_mm=spacing,
                                        candidates=len(grid.xyz),
                                        solver=solver,
                                        method=method,
                                        status="geometry_truth_sensitivity",
                                        **ident,
                                        **source_metrics(
                                            estimates[:, col],
                                            grid,
                                            truth,
                                            int(ident["source"]),
                                            method,
                                        ),
                                    )
                                )
                except (
                    ValueError,
                    ArithmeticError,
                    subprocess.SubprocessError,
                    MemoryError,
                    TimeoutError,
                ) as exc:
                    row["reason"] = failure(exc, output / (label + "-batch0"))
                    for method, source, std, draw in itertools.product(
                        ["Tikhonov", "MNE", "dSPM"], range(12), [0.0, 5e-8, 1.5e-7], range(8)
                    ):
                        if std == 0 and draw:
                            continue
                        inverse.append(
                            dict(
                                head=head,
                                spacing_mm=spacing,
                                candidates=len(grid.xyz),
                                solver=solver,
                                method=method,
                                source=source,
                                noise_std_V=std,
                                draw=draw,
                                status="FAILED",
                                reason=row["reason"],
                            )
                        )
                models.append(row)
                print(label, row["status"], flush=True)
    for name, rows in [
        ("models", models),
        ("comparisons", comparisons),
        ("geometry", geometry_rows),
        ("resolutions", resolutions),
        ("peaks", peaks),
    ]:
        (output / (name + ".json")).write_text(json.dumps(rows, indent=2) + "\n")
    pd.DataFrame(inverse).to_csv(output / "inverse.csv", index=False)
    pd.DataFrame(psfs).to_csv(output / "point-spread.csv", index=False)
    pd.DataFrame(source_rows).to_csv(output / "forward-sources.csv", index=False)
    for label, g in fields.items():
        np.savetxt(output / (label + "-V_per_Am.csv"), g, delimiter=",")
    finest = [r for r in comparisons if r["condition"] == "B matched" and r["level"] == 3]
    receipt = dict(
        schema="soma.mesh-grid.receipt/1",
        protocol=sealed.protocol.fingerprint,
        synthetic_only=True,
        human_subjects=0,
        computed_fields=sum(r["status"] == "computed" for r in models),
        failed_fields=sum(r["status"] != "computed" for r in models),
        inverse_rows=len(inverse),
        heads=6,
        sources_per_head=12,
        grids=4,
        seconds=time.perf_counter() - started,
        matched_finest_pass=len(finest) == 6 and all(r["relative"] <= 0.1 for r in finest),
        matched_finest_relative=[r["relative"] for r in finest],
        threshold=0.1,
        parent_commit=c["parent_commit"],
        parent_prs=[14, 13],
        phantom="NOT_AVAILABLE",
        human_accuracy="NOT_ESTABLISHED",
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
