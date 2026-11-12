"""Permission-free synthetic solver orchestration, isolated from model environments."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from soma.geometry import Frame
from soma.imaging.mesh_quality import _point_triangle, contains
from soma.imaging.surfaces import Mesh
from soma.source.nonspherical import Array, design, mesh_fingerprint, validate_meshes


def solve(
    boundaries: list[Mesh],
    points: Array,
    sensors: Array,
    conductivities: list[float],
    output: Path,
    *,
    solver: str = "openmeeg",
    conductivity_unit: str = "S/m",
) -> tuple[Array, dict[str, Any]]:
    c = design()
    if conductivity_unit != "S/m":
        raise ValueError("Conductivity unit must be S/m")
    if solver not in {"openmeeg", "mne"}:
        raise ValueError("Unsupported solver")
    if len(boundaries) == 4:
        validate_meshes(boundaries)
    if len(boundaries) not in (1, 3, 4) or len(conductivities) != len(boundaries):
        raise ValueError("Incompatible conductor topology")
    if any(m.vertices.frame != Frame.MRI for m in boundaries):
        raise ValueError("Solver requires MRI metres")
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or not 1 <= len(points) <= 80
        or not np.isfinite(points).all()
    ):
        raise ValueError("Invalid Cartesian dipoles")
    if (
        sensors.ndim != 2
        or sensors.shape[1] != 3
        or not 4 <= len(sensors) <= 64
        or not np.isfinite(sensors).all()
    ):
        raise ValueError("Invalid sensor coordinates")
    if any(not np.isfinite(x) or not 0 < x <= 3 for x in conductivities):
        raise ValueError("Conductivity must be finite positive S/m")
    if not contains(boundaries[0], points).all():
        raise ValueError("Invalid geometry: dipoles outside brain")
    tri = boundaries[-1].vertices.xyz[boundaries[-1].faces]
    if any(_point_triangle(np.broadcast_to(p, (len(tri), 3)), tri).min() > 1e-7 for p in sensors):
        raise ValueError("Invalid geometry: sensors must lie on discrete scalp")
    output.mkdir(parents=True, exist_ok=False)
    arrays: dict[str, Any] = {"points": points, "sensors": sensors}
    for i, m in enumerate(boundaries):
        arrays[f"v{i}"] = m.vertices.xyz
        arrays[f"f{i}"] = m.faces
    packet = output / "input.npz"
    np.savez_compressed(packet, **arrays)
    request = {
        "packet": str(packet.resolve()),
        "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
        "solver": solver,
        "layers": len(boundaries),
        "conductivities_S_m": conductivities,
        "conductivity_unit": "S/m",
    }
    path = output / "request.local.json"
    path.write_text(json.dumps(request))
    worker = Path(__file__).with_name("nonspherical_worker.py")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "VIRTUAL_ENV", "SOMA_EXPLORER_CONFIG"}
    }
    env.update(
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(worker), str(path), str(output / "result")],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=c["per_solver_timeout_s"],
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Resource exhaustion: frozen solver time budget") from exc
    (output / "solver.log").write_text(result.stdout)
    if result.returncode:
        error = (
            next(
                (line for line in reversed(result.stdout.splitlines()) if line.strip()),
                "no diagnostic",
            )
            if result.stdout
            else "solver failed without diagnostic"
        )
        raise ValueError("Forward-solver failure: " + error)
    lead = np.load(output / "result/lead.npy", allow_pickle=False)
    if lead.shape != (len(sensors), 3 * len(points)) or not np.isfinite(lead).all():
        raise ValueError("Incomplete solver output")
    d = json.loads((output / "result/diagnostics.json").read_text())
    d.update(
        mesh_fingerprint=mesh_fingerprint(boundaries),
        worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
        packet_sha256=request["packet_sha256"],
        lead_sha256=hashlib.sha256(lead.tobytes()).hexdigest(),
    )
    return np.asarray(lead, dtype=float), d
