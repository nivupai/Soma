"""Bounded private MRI-derived geometry/BEM execution, no implicit download."""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import mne
import numpy as np

from soma.anatomy.surfaces import ConductorSurfaces, distance_to_surface
from soma.datasets.human_mri import safe_local_output
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains


def run(target, level, solver, geometry_only):
    safe_local_output(target)
    target.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    assets = SampleAssets()
    info = assets.eeg_info()
    native = mne.make_bem_model(
        assets.subject,
        ico=level,
        conductivity=(0.3, 0.006, 0.3),
        subjects_dir=assets.subjects_dir,
        verbose=False,
    )
    surfaces = ConductorSurfaces.from_mne(
        assets.subject,
        native,
        {
            "source": "distributed participant FLASH derivatives",
            "level": level,
            "reference_truth": False,
        },
    )
    check = surfaces.readiness(
        sensor_compatible=None, minimum_separation_m=0.0001, minimum_quality=0.01
    )
    geometry_ok = all(
        v["status"] == "PASS"
        for k, v in check["checks"].items()
        if k not in ["anatomical_evidence", "sensor_compatibility"]
    )
    raw = np.array([ch["loc"][:3] for ch in info["chs"]])
    sensor = assets.transform.apply(Points(raw, Frame.HEAD))
    d = distance_to_surface(sensor, surfaces.meshes[-1])
    arrays = {}
    for i, b in enumerate(surfaces.meshes):
        arrays[f"v{i}"] = b.vertices.xyz
        arrays[f"f{i}"] = b.faces
    np.savez_compressed(target / "geometry.npz", **arrays)
    record = {
        "level": level,
        "surface_geometry_pass": geometry_ok,
        "surface_checks": check,
        "EEG_channels": len(raw),
        "electrode_scalp_max_mm": float(d.max() * 1000),
        "electrode_scalp_RMS_mm": float(np.sqrt(np.mean(d * d)) * 1000),
        "sensor_inside_scalp_count": int(contains(surfaces.meshes[-1], sensor.xyz).sum()),
        "sensor_gate_pass": bool(d.max() <= 0.03),
        "solver": solver,
    }
    if not geometry_only:
        if not geometry_ok or not record["sensor_gate_pass"]:
            raise ValueError("NOT_READY_FOR_FORWARD_MODEL: geometry or electrode gate")
        with np.load(target.parent / "sources.npz", allow_pickle=False) as z:
            rr = z["sources_m"]
        margin = distance_to_surface(Points(rr, Frame.MRI), surfaces.meshes[0])
        inside = contains(surfaces.meshes[0], rr)
        if not inside.all() or margin.min() < 0.005 - 1e-10:
            raise ValueError("Source containment/margin gate failed; no source removal")
        src = mne.setup_volume_source_space(
            pos={"rr": rr, "nn": np.tile([0.0, 0.0, 1.0], (len(rr), 1))},
            sphere=(0.0, 0.0, 0.0, 0.2),
            add_interpolator=False,
            verbose=False,
        )
        if any(int(s["coord_frame"]) != 5 for s in src):
            raise ValueError("Source frame is not MRI surface RAS")
        bem = mne.make_bem_solution(native, solver=solver, verbose=False)
        forward = mne.make_forward_solution(
            info,
            trans=assets.transform.to_mne(),
            src=src,
            bem=bem,
            eeg=True,
            meg=False,
            mindist=0,
            n_jobs=1,
            verbose=False,
        )
        expected_head = assets.transform.inverse().apply(Points(rr, Frame.MRI)).xyz
        if forward["nsource"] != len(rr) or not np.allclose(
            forward["source_rr"], expected_head, rtol=0, atol=1e-7
        ):
            raise ValueError("Forward removed/reordered source locations")
        # MNE free Cartesian coefficients are head XYZ; explicitly rotate to MRI XYZ.
        g = forward["sol"]["data"].reshape(len(raw), -1, 3) @ assets.transform.matrix[:3, :3].T
        g = g.reshape(len(raw), -1)
        p = np.eye(len(raw)) - np.ones((len(raw), len(raw))) / len(raw)
        g = p @ g
        if not np.isfinite(g).all() or np.max(abs(g.mean(axis=0))) > 1e-10:
            raise ValueError("Invalid average-referenced field")
        sv = np.linalg.svd(g, compute_uv=False)
        nonzero = sv > sv[0] * 1e-12
        np.savetxt(target / "lead-V_per_Am.csv", g, delimiter=",")
        record.update(
            source_count=len(rr),
            source_margin_min_mm=float(margin.min() * 1000),
            lead_rank=int(nonzero.sum()),
            lead_nonnull_condition=float(sv[0] / sv[nonzero][-1]),
            reference_mean_max_V_per_Am=float(abs(g.mean(axis=0)).max()),
            source_head_pairing_max_m=float(abs(forward["source_rr"] - expected_head).max()),
            frame="MRI_surface_RAS_m",
            orientation_order="source-major XYZ",
            units="V/(A*m)",
            human_source_accuracy=False,
            solver_residual="not independently exposed by the MNE BEM solution API; not invented",
        )
    record["seconds"] = time.perf_counter() - start
    record["peak_MiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
        1024**2 if sys.platform == "darwin" else 1024
    )
    if record["peak_MiB"] > 4096:
        raise MemoryError("Frozen worker memory budget")
    (target / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    print("Private MRI model stage completed", level, solver, geometry_only)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("target", type=Path)
    p.add_argument("--level", type=int, choices=[2, 3, 4], required=True)
    p.add_argument("--solver", choices=["mne", "openmeeg"], default="mne")
    p.add_argument("--geometry-only", action="store_true")
    a = p.parse_args()
    run(a.target, a.level, a.solver, a.geometry_only)
