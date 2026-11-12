"""Isolated optional solver: pinned OpenMEEG symmetric BEM or independent MNE LC."""

import argparse
import hashlib
import json
import resource
import sys
import time
import zipfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

import mne
import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.linalg.lapack import dgecon

from soma.source.noise import average_projector
from soma.source.nonspherical import design


def calculate(packet: Path, request: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    with zipfile.ZipFile(packet) as z:
        if sum(x.file_size for x in z.infolist()) > 8 * 1024**2:
            raise ValueError("Bounded numerical packet exceeded")
    with np.load(packet, allow_pickle=False) as z:
        arrays = {n: z[n] for n in z.files}
    if any(a.dtype.kind not in "fiu" or not np.isfinite(a).all() for a in arrays.values()):
        raise ValueError("Only finite numerical solver inputs")
    n = request["layers"]
    c = design()
    points = arrays["points"]
    sensors = arrays["sensors"]
    sigmas = request["conductivities_S_m"]
    if (
        n not in (1, 3, 4)
        or request["conductivity_unit"] != "S/m"
        or len(sigmas) != n
        or any(not np.isfinite(x) or not 0 < x <= 3 for x in sigmas)
        or points.ndim != 2
        or points.shape[1] != 3
        or len(points) > 80
        or sensors.ndim != 2
        or sensors.shape[1] != 3
        or not 4 <= len(sensors) <= 64
    ):
        raise ValueError("Invalid physical solver contract")
    raw_meshes = [(arrays[f"v{i}"], arrays[f"f{i}"]) for i in range(n)]
    started = time.perf_counter()
    if request["solver"] == "mne":
        if n != 3:
            raise ValueError("Unsupported topology: MNE independent EEG control requires 3 layers")
        surfaces = []
        for i, (v, f) in enumerate(raw_meshes):
            surface = dict(
                id=[1, 3, 4][i],
                rr=v,
                tris=f,
                np=len(v),
                ntri=len(f),
                sigma=sigmas[i],
                coord_frame=5,
            )
            surfaces.append(mne.surface.complete_surface_info(surface, copy=True, verbose=False))
        bem = mne.make_bem_solution(surfaces[::-1], solver="mne", verbose=False)
        names = [f"E{i:02}" for i in range(len(sensors))]
        info = mne.create_info(names, 160, "eeg")
        info.set_montage(
            mne.channels.make_dig_montage(
                ch_pos=dict(zip(names, sensors, strict=True)), coord_frame="head"
            )
        )
        src = mne.setup_volume_source_space(
            pos=dict(rr=points, nn=np.tile([0.0, 0.0, 1.0], (len(points), 1))),
            sphere=(0.0, 0.0, 0.0, 0.1),
            add_interpolator=False,
            verbose=False,
        )
        fwd = mne.make_forward_solution(
            info,
            trans=mne.transforms.Transform("mri", "head", np.eye(4)),
            src=src,
            bem=bem,
            meg=False,
            eeg=True,
            mindist=0,
            n_jobs=1,
            verbose=False,
        )
        if fwd["sol"]["data"].shape != (len(sensors), 3 * len(points)) or not np.allclose(
            fwd["source_rr"], points, atol=1e-9
        ):
            raise ValueError("Independent MNE source pairing changed")
        unreferenced = np.asarray(fwd["sol"]["data"], dtype=float)
        diagnostics = {
            "solver": "MNE linear collocation",
            "solver_version": mne.__version__,
            "system_residual_scope": "MNE diagnostics not exposed; no fabricated PDE residual",
            "independent_codebase_from_OpenMEEG": True,
        }
    elif request["solver"] == "openmeeg":
        if version("openmeeg") != "2.6.0":
            raise ValueError("Pinned OpenMEEG 2.6.0 required")
        import openmeeg as om
        from openmeeg._openmeeg_wrapper import OrientedMesh, SimpleDomain

        meshes = {
            f"S{i}": (v, np.asarray(f[:, [1, 0, 2]], dtype=np.int64))
            for i, (v, f) in enumerate(raw_meshes)
        }
        interfaces = {name: [(name, OrientedMesh.Normal)] for name in meshes}
        names = list(meshes)
        domains = {
            "Brain": ([(names[0], SimpleDomain.Inside)], sigmas[0]),
            "Air": ([(names[-1], SimpleDomain.Outside)], 0.0),
        }
        for i in range(1, n):
            domains[f"Layer{i}"] = (
                [(names[i - 1], SimpleDomain.Outside), (names[i], SimpleDomain.Inside)],
                sigmas[i],
            )
        unknowns = sum(len(v) for v, f in raw_meshes) + sum(len(f) for v, f in raw_meshes[:-1])
        estimated = unknowns**2 * 8 * 4
        if unknowns > c["max_dense_unknowns"] or estimated > c["max_estimated_dense_bytes"]:
            raise MemoryError("Frozen dense resource budget exceeded")
        geom = om.make_geometry(meshes, interfaces, domains)
        integ = c["integrator"]
        integrator = om.Integrator(integ["order"], integ["adaptive_levels"], integ["tolerance"])
        hm = om.HeadMat(geom, integrator)
        a = om.Matrix(hm).array()
        dipoles = np.column_stack(
            [np.repeat(points, 3, axis=0), np.tile(np.eye(3), (len(points), 1))]
        )
        b = om.DipSourceMat(
            geom, om.Matrix(np.asfortranarray(dipoles)), integrator, "Brain"
        ).array()
        sensor = om.make_sensors(sensors, geometry=geom)
        h = om.Matrix(om.Head2EEGMat(geom, sensor)).array()
        symmetry = float(np.linalg.norm(a - a.T) / np.linalg.norm(a))
        anorm = float(np.linalg.norm(a, 1))
        lu, piv = lu_factor(a, check_finite=True)
        x = lu_solve((lu, piv), b)
        residual = float(np.linalg.norm(a @ x - b) / np.linalg.norm(b))
        rcond, _ = dgecon(lu, anorm)
        denominator = np.linalg.norm(b[:, 0]) * np.linalg.norm(x[:, 1]) + np.linalg.norm(
            b[:, 1]
        ) * np.linalg.norm(x[:, 0])
        reciprocity = float(
            abs(b[:, 0] @ x[:, 1] - b[:, 1] @ x[:, 0]) / max(float(denominator), 1e-30)
        )
        if (
            symmetry > c["symmetry_rtol"]
            or residual > c["solver_residual_rtol"]
            or reciprocity > c["reciprocity_rtol"]
            or not np.isfinite(x).all()
        ):
            raise ArithmeticError("Forward solver nonconvergence or symmetry/reciprocity failure")
        unreferenced = h @ x
        diagnostics = {
            "solver": "OpenMEEG symmetric BEM / SciPy pivoted LU",
            "solver_version": version("openmeeg"),
            "layers": n,
            "unknowns": unknowns,
            "estimated_dense_bytes": estimated,
            "assembly_symmetry_relative": symmetry,
            "algebraic_residual_relative": residual,
            "algebraic_reciprocity_relative": reciprocity,
            "reciprocal_condition_estimate_mixed_units": float(rcond),
            "residual_scope": "mixed potential/current discrete BEM system; not FEM PDE residual",
            "integrator": integ,
        }
    else:
        raise ValueError("Unsupported solver")
    if unreferenced.shape != (len(sensors), 3 * len(points)) or not np.isfinite(unreferenced).all():
        raise ArithmeticError("Incomplete or nonfinite forward")
    p = average_projector(len(sensors))
    lead = p @ unreferenced
    s = np.linalg.svd(lead, compute_uv=False)
    keep = s > s[0] * max(lead.shape) * np.finfo(float).eps
    diagnostics.update(
        runtime_seconds=time.perf_counter() - started,
        process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (2**20 if sys.platform == "darwin" else 1024),
        rank=int(keep.sum()),
        retained_condition=float(s[0] / s[keep][-1]),
        singular_values=s.tolist(),
        reference_null_relative=float(np.linalg.norm(lead.sum(axis=0)) / np.linalg.norm(lead)),
        reference_reprojection_relative=float(
            np.linalg.norm(p @ (unreferenced - unreferenced[:1]) - lead) / np.linalg.norm(lead)
        ),
        units="V/(A m)",
        solver_frame="MRI RAS metres; declared coincident head for calculation",
    )
    return lead, diagnostics


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("request", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    q = json.loads(a.request.read_text())
    packet = Path(q["packet"])
    if hashlib.sha256(packet.read_bytes()).hexdigest() != q["packet_sha256"]:
        raise ValueError("Changed solver packet")
    lead, diagnostics = calculate(packet, q)
    a.output.mkdir(exist_ok=False)
    np.save(a.output / "lead.npy", lead, allow_pickle=False)
    (a.output / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
