"""M33 forward-model revalidation on MNE sample with the cortical source space.

Rebuilds the EEG lead field (M32 conductivities, fixed normal orientation) on the oct6
cortical midsurface source space, runs a BEM mesh refinement study and compares the
MNE and OpenMEEG BEM solutions on the same surfaces and sources.

Each stage runs in its own subprocess, one at a time, and is skipped when its output
already exists (resumable). Private arrays stay under the git-ignored ``--work`` tree;
the public JSON holds aggregates only (no paths, coordinates or fingerprints).

Levels: ``3`` and ``4`` are MNE ico decimations of the provided ico4 (2562-vertex)
FLASH surfaces, exactly as in M32. ``5i`` keeps the level-4 geometry and splits every
inner-skull triangle into four (outer skull and scalp stay at level 4): finer than the
provided surfaces cannot add geometry, only discretization. Full level 5 (all three
surfaces subdivided, 30726 unknowns, ~7.5 GB per dense BEM matrix copy) is not run on
a 16 GB machine.
"""

import argparse
import hashlib
import json
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.anatomy.surfaces import ConductorSurfaces, distance_to_surface
from soma.datasets.human_mri import safe_local_output
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains
from soma.source.cortical import HemisphereSurfaces, build_cortical_source_space
from soma.source.forward_revalidation import (
    REFINEMENT_TARGET,
    average_reference,
    fixed_orientation,
    margin_strata,
    minimum_mesh_level,
    per_source,
    readiness_tag,
    relative_change,
    subdivide_midpoint,
    summarize,
)

CONDUCTIVITY = (0.3, 0.006, 0.3)  # M32 brain/skull/scalp, S/m
LEVELS = ("3", "4", "5i")
STAGES = [("3", "mne"), ("4", "mne"), ("5i", "mne"), ("3", "openmeeg"), ("4", "openmeeg")]
CHUNK = 1000
MEMORY_BUDGET_MIB = 9000
MARGIN_EDGES_MM = (0.0, 1.0, 2.0, 5.0, 10.0)
IMPLEMENTATION = [
    "scripts/run_forward_revalidation.py",
    "src/soma/source/forward_revalidation.py",
    "src/soma/source/cortical.py",
]
READINESS = readiness_tag("QC_ONLY_ANATOMY", skull_ct_validated=False)


def peak_mib() -> float:
    scale = 1024**2 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale


def bem_model(assets: SampleAssets, level: str, work: Path) -> Any:
    if level in ("3", "4"):
        return mne.make_bem_model(
            assets.subject,
            ico=int(level),
            conductivity=CONDUCTIVITY,
            subjects_dir=assets.subjects_dir,
            verbose=False,
        )
    if level != "5i":
        raise ValueError(level)
    subjects = work / "subjects"
    bem = subjects / "sample5i" / "bem"
    if not (bem / "inner_skull.surf").is_file():
        bem.mkdir(parents=True, exist_ok=True)
        source = assets.subject_dir / "bem"
        rr, tris = mne.read_surface(source / "inner_skull.surf", verbose=False)
        rr5, tris5 = subdivide_midpoint(rr, tris.astype(np.int64))
        mne.write_surface(bem / "inner_skull.surf", rr5, tris5, overwrite=True)
        for name in ("outer_skull.surf", "outer_skin.surf"):
            shutil.copyfile(source / name, bem / name)
    return mne.make_bem_model(
        "sample5i", ico=None, conductivity=CONDUCTIVITY, subjects_dir=subjects, verbose=False
    )


def conductor(model: Any, level: str) -> ConductorSurfaces:
    return ConductorSurfaces.from_mne(
        "sample", model, {"source": "distributed participant FLASH derivatives", "level": level}
    )


def stage_sources(assets: SampleAssets, work: Path) -> dict[str, Any]:
    hemis = [HemisphereSurfaces.from_freesurfer(assets.subject_dir, h) for h in ("lh", "rh")]
    bem_path = assets.subject_dir / "bem/sample-5120-5120-5120-bem.fif"
    skull = ConductorSurfaces.from_mne(
        "sample", mne.read_bem_surfaces(bem_path, verbose=False), {"source": "subject BEM"}
    ).meshes[0]
    space = build_cortical_source_space(hemis, skull, spacing="oct6")
    np.savez(
        work / "sources.npz",
        positions_m=space.positions_m,
        normals=space.normals,
        areas_m2=space.areas_m2,
    )
    return {"sources": len(space.positions_m), "identity_sha256": space.identity}


def stage_geometry(assets: SampleAssets, work: Path) -> dict[str, Any]:
    with np.load(work / "sources.npz") as z:
        rr = z["positions_m"]
    info = assets.eeg_info()
    raw = np.array([ch["loc"][:3] for ch in info["chs"]])
    sensors = assets.transform.apply(Points(raw, Frame.HEAD))
    inside = np.ones(len(rr), bool)
    levels: dict[str, Any] = {}
    margin4 = None
    for level in LEVELS:
        surfaces = conductor(bem_model(assets, level, work), level)
        check = surfaces.readiness(sensor_compatible=None)
        ok = all(
            v["status"] == "PASS"
            for k, v in check["checks"].items()
            if k not in ["anatomical_evidence", "sensor_compatibility"]
        )
        skull = surfaces.meshes[0]
        inn = contains(skull, rr)
        margin = distance_to_surface(Points(rr, Frame.MRI), skull)
        if level == "4":
            margin4 = margin
        d = distance_to_surface(sensors, surfaces.meshes[-1])
        inside &= inn
        levels[level] = {
            "surface_geometry_pass": bool(ok),
            "vertex_counts": [len(m.vertices.xyz) for m in surfaces.meshes],
            "face_counts": [len(m.faces) for m in surfaces.meshes],
            "triangle_quality_min": [float(q["triangle_quality_min"]) for q in check["quality"]],
            "sources_inside_inner_skull": int(inn.sum()),
            "inside_margin_min_mm": float(margin[inn].min() * 1000),
            "electrode_scalp_max_mm": float(d.max() * 1000),
            "electrode_gate_pass": bool(d.max() <= 0.03),
        }
        if not ok or d.max() > 0.03:
            raise ValueError(f"NOT_READY_FOR_FORWARD_MODEL at level {level}")
    assert margin4 is not None
    np.savez(work / "common.npz", inside=inside, margin4_m=margin4)
    return {"levels": levels, "common_sources": int(inside.sum()), "EEG_channels": len(raw)}


def stage_forward(assets: SampleAssets, work: Path, level: str, solver: str) -> dict[str, Any]:
    start = time.perf_counter()
    with np.load(work / "sources.npz") as z:
        rr_all, nn_all = z["positions_m"], z["normals"]
    with np.load(work / "common.npz") as z:
        keep = z["inside"]
    rr, nn = rr_all[keep], nn_all[keep]
    info = assets.eeg_info()
    model = bem_model(assets, level, work)
    unknowns = sum(len(s["rr"]) for s in model)
    t0 = time.perf_counter()
    bem = mne.make_bem_solution(model, solver=solver, verbose=False)
    solve_seconds = time.perf_counter() - t0
    trans = assets.transform.to_mne()
    rotation = assets.transform.matrix[:3, :3]
    columns = []
    for lo in range(0, len(rr), CHUNK):
        part = slice(lo, lo + CHUNK)
        src = mne.setup_volume_source_space(
            pos={"rr": rr[part], "nn": nn[part]},
            sphere=(0.0, 0.0, 0.0, 0.2),
            add_interpolator=False,
            verbose=False,
        )
        fwd = mne.make_forward_solution(
            info, trans=trans, src=src, bem=bem, eeg=True, meg=False, mindist=0, verbose=False
        )
        expected = assets.transform.inverse().apply(Points(rr[part], Frame.MRI)).xyz
        if fwd["nsource"] != len(expected) or not np.allclose(
            fwd["source_rr"], expected, rtol=0, atol=1e-7
        ):
            raise ValueError("Forward removed/reordered source locations")
        columns.append(fixed_orientation(fwd["sol"]["data"], nn[part], rotation))
        del fwd, src
    g = average_reference(np.hstack(columns))
    if not np.isfinite(g).all():
        raise ValueError("Non-finite lead field")
    sv = np.linalg.svd(g, compute_uv=False)
    nonzero = sv > sv[0] * 1e-12
    np.save(work / f"lead-{level}-{solver}.npy", g)
    record = {
        "level": level,
        "solver": solver,
        "bem_unknown_vertices": int(unknowns),
        "source_count": int(g.shape[1]),
        "EEG_channels": int(g.shape[0]),
        "orientation": "fixed cortical normal",
        "lead_rank": int(nonzero.sum()),
        "lead_nonnull_condition": float(sv[0] / sv[nonzero][-1]),
        "bem_solution_seconds": solve_seconds,
        "seconds": time.perf_counter() - start,
        "peak_MiB": peak_mib(),
        "units": "V/(A*m)",
        "readiness": READINESS["head_readiness"],
    }
    if record["peak_MiB"] > MEMORY_BUDGET_MIB:
        raise MemoryError("Worker memory budget exceeded")
    return record


def free_memory_percent() -> int:
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True, check=True).stdout
    line = [x for x in out.splitlines() if "free percentage" in x][-1]
    return int(line.rsplit(":", 1)[1].strip().rstrip("%"))


def run_stage(work: Path, name: str, args: list[str], log: Any) -> dict[str, Any]:
    receipt = work / f"{name}.json"
    if receipt.is_file():
        print(f"skip {name} (exists)", file=log, flush=True)
        return dict(json.loads(receipt.read_text()))
    while sys.platform == "darwin" and free_memory_percent() < 25:
        print(f"waiting for memory before {name}", file=log, flush=True)
        time.sleep(60)
    print(f"start {name} {time.strftime('%H:%M:%S')}", file=log, flush=True)
    cmd = [sys.executable, __file__, "--work", str(work), "--root", str(ROOT), "--stage", *args]
    result = subprocess.run(cmd, stdout=log, stderr=log, check=False)
    if result.returncode or not receipt.is_file():
        failure = {"stage": name, "status": "FAILED", "returncode": result.returncode}
        print(json.dumps(failure), file=log, flush=True)
        return failure
    print(f"done {name} {time.strftime('%H:%M:%S')}", file=log, flush=True)
    return dict(json.loads(receipt.read_text()))


def aggregate(work: Path, receipts: dict[str, Any]) -> dict[str, Any]:
    leads = {
        (lv, s): np.load(work / f"lead-{lv}-{s}.npy")
        for lv, s in STAGES
        if (work / f"lead-{lv}-{s}.npy").is_file()
    }
    with np.load(work / "common.npz") as z:
        margin = z["margin4_m"][z["inside"]]
    refinement = []
    for coarse, fine in [("3", "4"), ("4", "5i")]:
        if (coarse, "mne") not in leads or (fine, "mne") not in leads:
            refinement.append({"coarse": coarse, "fine": fine, "status": "NOT_RUN"})
            continue
        a, b = leads[coarse, "mne"], leads[fine, "mne"]
        rel = relative_change(a, b)
        ps = per_source(a, b)
        refinement.append(
            {
                "coarse": coarse,
                "fine": fine,
                "solver": "mne",
                "relative": rel,
                "target": REFINEMENT_TARGET,
                "passed": rel < REFINEMENT_TARGET,
                "per_source_relative_error": summarize(ps["relative_error"]),
                "per_source_correlation": summarize(ps["correlation"]),
                "by_inner_skull_margin": margin_strata(a, b, margin, MARGIN_EDGES_MM),
                "anatomical_accuracy": False,
                **READINESS,
            }
        )
    done = [(r["coarse"], r["fine"], r["relative"]) for r in refinement if "relative" in r]
    chain_complete = len(done) == len(refinement)
    agreement = []
    for level in ("3", "4"):
        if (level, "openmeeg") not in leads or (level, "mne") not in leads:
            agreement.append({"level": level, "status": "NOT_RUN"})
            continue
        a, b = leads[level, "mne"], leads[level, "openmeeg"]
        ps = per_source(a, b)
        agreement.append(
            {
                "level": level,
                "comparison": "MNE linear collocation vs OpenMEEG symmetric BEM",
                "reference": "openmeeg",
                "relative": relative_change(a, b),
                "target": REFINEMENT_TARGET,
                "passed": relative_change(a, b) < REFINEMENT_TARGET,
                "per_source_relative_error": summarize(ps["relative_error"]),
                "per_source_correlation": summarize(ps["correlation"]),
                "per_source_log_magnitude_ratio": summarize(ps["log_magnitude_ratio"]),
                "by_inner_skull_margin": margin_strata(a, b, margin, MARGIN_EDGES_MM),
                "ground_truth_error": False,
                **READINESS,
            }
        )
    minimum = minimum_mesh_level(done) if chain_complete and done else None
    by_margin = []
    if chain_complete and done:
        for k, edge in enumerate(MARGIN_EDGES_MM):
            chain = [
                (r["coarse"], r["fine"], r["by_inner_skull_margin"][k]["relative"])
                for r in refinement
            ]
            by_margin.append(
                {
                    "minimum_margin_mm": edge,
                    "sources": refinement[0]["by_inner_skull_margin"][k]["sources"],
                    "minimum_human_mesh_level": minimum_mesh_level(chain),
                }
            )
    return {
        "refinement": refinement,
        "minimum_human_mesh_level": minimum,
        "minimum_human_mesh_level_by_source_margin": by_margin,
        "margin_strata_prespecified": True,
        "two_finest_levels_pass": bool(done and chain_complete and done[-1][2] < 0.1),
        "solver_agreement": agreement,
        "margin_stratum_reference": "unsigned distance to the level-4 inner skull",
    }


def orchestrate(work: Path, output: Path) -> None:
    start = time.perf_counter()
    work.mkdir(parents=True, exist_ok=True)
    safe_local_output(work)
    with (work / "progress.log").open("a") as log:
        receipts = {
            "sources": run_stage(work, "sources", ["sources"], log),
            "geometry": run_stage(work, "geometry", ["geometry"], log),
        }
        if "FAILED" in (receipts["sources"].get("status"), receipts["geometry"].get("status")):
            raise SystemExit("Source or geometry stage failed; see progress.log")
        for level, solver in STAGES:
            name = f"forward-{level}-{solver}"
            receipts[name] = run_stage(work, name, ["forward", level, solver], log)
        results = aggregate(work, receipts)
    with np.load(work / "common.npz") as z:
        margin = z["margin4_m"][z["inside"]]
    public = {
        "schema": "soma.forward-revalidation/1",
        "subject": "MNE sample (public dataset)",
        **READINESS,
        "conductor": "three-compartment BEM (brain/CSF homogenized), provided FLASH surfaces",
        "conductivity_S_per_m": dict(zip(["brain", "skull", "scalp"], CONDUCTIVITY, strict=True)),
        "modality": "EEG, average reference",
        "source_space": {
            "kind": "cortical white/pial midsurface, oct6 (soma.source.cortical)",
            "orientation": "fixed, area-weighted outward midsurface normal",
            "built_sources": receipts["sources"]["sources"],
            "common_sources_inside_every_level": receipts["geometry"]["common_sources"],
            "selection": "sources inside the inner skull of every compared level; none moved",
            "inner_skull_margin_level4_mm": summarize(margin * 1000),
        },
        "levels": {
            "3": "MNE ico3 decimation of the provided surfaces (642 vertices each)",
            "4": "provided ico4 surfaces (2562 vertices each)",
            "5i": "level-4 geometry; inner skull midpoint-subdivided (10242 vertices), "
            "outer skull/scalp level 4; discretization-only refinement",
            "5": "INFEASIBLE here: 30726 BEM unknowns, ~7.5 GB per dense matrix copy (MNE), "
            "larger for OpenMEEG, on a 16 GB machine",
            "openmeeg_5i": "not run: ~41k OpenMEEG unknowns, dense matrix exceeds memory",
        },
        "metric": "||G_coarse - G_fine||_F / ||G_fine||_F on average-referenced fixed-"
        "orientation lead fields (M32 metric); solver agreement uses OpenMEEG as reference",
        "geometry": receipts["geometry"]["levels"],
        "EEG_channels": receipts["geometry"]["EEG_channels"],
        "forward": [receipts[f"forward-{lv}-{s}"] for lv, s in STAGES],
        **results,
        "M32_baseline": {
            "source_space": "volumetric, 140 sources, free orientation",
            "refinement2to3": 0.14562012613874192,
            "refinement3to4": 0.05117222825165996,
            "matched_BEM_MNE_OpenMEEG_level3": 0.06813307790734653,
        },
        "anatomical_accuracy": False,
        "human_source_accuracy": False,
        "implementation_sha256": {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in IMPLEMENTATION
        },
        "mne_version": mne.__version__,
        "orchestrator_seconds": time.perf_counter() - start,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    print("wrote", output)


ROOT = Path("data/raw/mne-sample")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("reports/m33-forward"))
    parser.add_argument("--root", type=Path, default=ROOT, help="folder with MNE-sample-data")
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/milestone33/forward-revalidation.json")
    )
    parser.add_argument("--stage", nargs="+")
    a = parser.parse_args()
    ROOT = a.root.resolve()
    if a.stage is None:
        orchestrate(a.work.resolve(), a.output)
    else:
        sample = SampleAssets(root=ROOT)
        kind = a.stage[0]
        if kind == "sources":
            name, rec = "sources", stage_sources(sample, a.work)
        elif kind == "geometry":
            name, rec = "geometry", stage_geometry(sample, a.work)
        else:
            name = f"forward-{a.stage[1]}-{a.stage[2]}"
            rec = stage_forward(sample, a.work, a.stage[1], a.stage[2])
        rec.setdefault("peak_MiB", peak_mib())
        (a.work / f"{name}.json").write_text(json.dumps(rec, indent=2) + "\n")
        print("stage complete", name)
