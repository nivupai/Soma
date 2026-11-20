"""Frozen local human-MRI study; only explicit whitelisted aggregates may be public."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from soma.anatomy.head_models import MRIFrameChain, classify_anatomy, require_forward_ready
from soma.anatomy.surfaces import distance_to_surface
from soma.datasets.human_mri import (
    align_t1,
    discover_human,
    load_human,
    mapped_reference,
    safe_local_output,
)
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points
from soma.imaging.mesh_quality import contains
from soma.imaging.surfaces import Mesh
from soma.source.domains import SourceDomain
from soma.source.noise import NoiseModel, average_projector
from soma.source.prior_calibration import PriorInverse, SourcePrior
from soma.validation.human_tissues import evaluate_human_subject

DESIGN_SHA = "89690086412e8682d4f4d19e7657644588b7e240590f15afd2dd464c3cf5d619"


def configuration():
    p = Path("experiments/milestone32/design.json")
    if hashlib.sha256(p.read_bytes()).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen M32 design changed")
    return json.loads(p.read_text())


def execute(target, level, solver="mne", geometry=False):
    target.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "scripts.mri_head_worker",
        str(target),
        "--level",
        str(level),
        "--solver",
        solver,
    ]
    if geometry:
        command += ["--geometry-only"]
    with (target / "worker.log").open("w") as stream:
        p = subprocess.run(
            command,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=600,
            check=False,
            env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"),
        )
    if p.returncode:
        raise RuntimeError("Private worker failed; preserved local log")
    return json.loads((target / "receipt.json").read_text())


def farthest(points, count):
    chosen = [int(np.argmin(np.linalg.norm(points - points.mean(axis=0), axis=1)))]
    distance = np.linalg.norm(points - points[chosen[0]], axis=1)
    for _ in range(count - 1):
        i = int(np.argmax(distance))
        chosen.append(i)
        distance = np.minimum(distance, np.linalg.norm(points - points[i], axis=1))
    if len(set(chosen)) != count:
        raise ValueError("Insufficient eligible MRI source cells")
    return np.array(chosen)


def tissue_study(local):
    inventory = discover_human(Path("data/external/ibsr"), Path("data/external/mrbrains"))
    (local / "inventory.private.json").write_text(json.dumps(inventory, indent=2) + "\n")
    rows = []
    failures = []
    confusion = []
    for i, record in enumerate(inventory["subjects"]):
        try:
            result = evaluate_human_subject(record, local / f"tissue-{i:03d}")
            rows.append(result)
            image = load_human(
                Path(record["image"]),
                dataset=record["dataset"],
                subject=record["subject"],
                role="intensity",
            )
            native = load_human(
                Path(record["reference"]),
                dataset=record["dataset"],
                subject=record["subject"],
                role="labels",
            )
            image, _ = align_t1(image, native, dataset=record["dataset"])
            ref, valid = mapped_reference(native, record["dataset"])
            pred = nib.load(local / f"tissue-{i:03d}" / "prediction.nii.gz").get_fdata().astype(int)
            truth = ref.array().astype(int)
            domain = valid.array().astype(bool)
            if record["dataset"] == "ibsr-v2":
                domain = np.ones(truth.shape, dtype=bool)
            counts = np.bincount((truth[domain] * 4 + pred[domain]).ravel(), minlength=16).reshape(
                4, 4
            )
            confusion.append(dict(dataset=record["dataset"], counts=counts.tolist()))
        except (ValueError, OSError) as exc:
            failures.append(
                dict(dataset=record["dataset"], stage="tissue", error=type(exc).__name__)
            )
        print("Tissue case", i, "complete", flush=True)
    (local / "tissue-results.private.json").write_text(json.dumps(rows, indent=2) + "\n")
    flat = [
        dict(dataset=r["dataset"], **{k: v for k, v in t.items() if k != "boundaries"})
        for r in rows
        for t in r["labels"]
    ]
    summary = (
        pd.DataFrame(flat)
        .groupby(["dataset", "label", "name"], dropna=False)
        .mean(numeric_only=True)
        .reset_index()
    )
    # Only aggregate numerical tissue summaries; no subject identifiers or input hashes.
    public = {
        "tissue_metrics": summary.to_dict("records"),
        "cohorts": [],
        "tissue_failures": failures,
        "confusion": [],
    }
    for dataset in ["ibsr-v2", "mrbrains13"]:
        group = [r for r in rows if r["dataset"] == dataset]
        bad = sum(
            not all(
                t["Dice"] >= 0.8 and t["HD95_mm"] is not None and t["HD95_mm"] <= 5
                for t in r["labels"]
            )
            for r in group
        )
        public["cohorts"].append(
            dict(
                dataset=dataset,
                completed=len(group),
                macro_Dice=float(np.mean([r["macro_Dice"] for r in group])) if group else None,
                reference_target_failed=bad,
                full_conductor_reference=False,
                forward_status="NOT_READY_FOR_FORWARD_MODEL",
                fresh_holdout=False,
            )
        )
        cc = sum(
            (np.array(x["counts"]) for x in confusion if x["dataset"] == dataset),
            np.zeros((4, 4), int),
        )
        total = cc.sum(axis=1, keepdims=True)
        norm = np.divide(cc, total, out=np.zeros_like(cc, float), where=total > 0)
        public["confusion"].append(
            dict(
                dataset=dataset,
                row_normalized=norm.tolist(),
                units="fraction; pooled voxels descriptive only",
            )
        )
    return public


def run(local):
    configuration()
    safe_local_output(local)
    local.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    implementation = {
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in [
            "scripts/run_mri_head_models.py",
            "scripts/mri_head_worker.py",
            "src/soma/anatomy/head_models.py",
            "src/soma/source/domains.py",
            "src/soma/source/prior_calibration.py",
            "src/soma/validation/human_tissues.py",
        ]
    }
    public = tissue_study(local)
    public["implementation_sha256"] = implementation
    failures = list(public["tissue_failures"])
    sample = SampleAssets()
    identity = sample.inspect()
    # All sensitive source identities/paths/fingerprints are private by construction.
    (local / "sample-identity.private.json").write_text(json.dumps(identity, indent=2) + "\n")
    image = nib.load(sample.subject_dir / "mri/T1.mgz")
    aseg = nib.load(sample.subject_dir / "mri/aseg.mgz")
    chain = MRIFrameChain.from_mgh(image, sample.transform)
    if image.shape != aseg.shape or not np.allclose(image.affine, aseg.affine, rtol=0, atol=1e-6):
        raise ValueError("Misaligned MRI segmentation: no implicit resampling")
    probes = np.array([[0, 0, 0], np.array(image.shape) / 2, np.array(image.shape) - 1], float)
    scanner = chain.apply(probes, "voxel_centers", "scanner_RAS_m")
    oracle = nib.affines.apply_affine(image.affine, probes) * 0.001
    surface = chain.apply(probes, "voxel_centers", "MRI_surface_RAS_m")
    back = chain.apply(
        chain.apply(surface, "MRI_surface_RAS_m", "head_m"), "head_m", "voxel_centers"
    )
    geometry = dict(
        scanner_oracle_max_m=float(abs(scanner - oracle).max()),
        roundtrip_voxel_max=float(abs(back - probes).max()),
        roundtrip_physical_max_m=float(
            abs(chain.apply(back, "voxel_centers", "MRI_surface_RAS_m") - surface).max()
        ),
        shape_matches=True,
        storage_axis_codes="".join(nib.aff2axcodes(image.affine)),
        spacing_min_mm=float(min(image.header.get_zooms())),
        spacing_max_mm=float(max(image.header.get_zooms())),
        frames=["voxel_centers", "scanner_RAS_m", "MRI_surface_RAS_m", "head_m"],
    )
    if geometry["scanner_oracle_max_m"] > 1e-10 or geometry["roundtrip_physical_max_m"] > 1e-10:
        raise ValueError("MRI coordinate gate")
    stages = {}
    meshes = {}
    for level in [2, 3, 4]:
        target = local / f"geometry-{level}"
        try:
            receipt = execute(target, level, geometry=True)
            stages[level] = receipt
            with np.load(target / "geometry.npz", allow_pickle=False) as z:
                meshes[level] = [
                    Mesh(Points(z[f"v{i}"], Frame.MRI), z[f"f{i}"], dict(MRI_derived=True))
                    for i in range(3)
                ]
        except (RuntimeError, subprocess.SubprocessError) as exc:
            failures.append(
                dict(dataset="mne-sample", stage=f"geometry-{level}", error=type(exc).__name__)
            )
        print("Geometry level", level, "complete", flush=True)
    if 3 not in stages or not stages[3]["surface_geometry_pass"]:
        public.update(
            anatomy_status="NOT_READY_FOR_FORWARD_MODEL",
            geometry=geometry,
            failures=failures,
            forward_executed=False,
        )
        finish(public, local, start)
        return
    good = [k for k, v in stages.items() if v["surface_geometry_pass"]]
    center = meshes[3][0].vertices.xyz.mean(axis=0)
    if not all(contains(meshes[k][0], center[None]).all() for k in good):
        raise ValueError("Conservative source-domain center is not intracranial")
    inside_radius = (
        min(
            float(distance_to_surface(Points(center[None], Frame.MRI), meshes[k][0])[0])
            for k in good
        )
        - 0.005
    )
    labels = np.asarray(aseg.dataobj)
    gm = np.isin(labels, [3, 42, 10, 49, 11, 50, 12, 51, 13, 52, 17, 53, 18, 54, 26, 58])
    ijk = np.argwhere(gm)
    xyz = chain.apply(ijk, "voxel_centers", "MRI_surface_RAS_m")
    eligible = np.linalg.norm(xyz - center, axis=1) < inside_radius
    mask = np.zeros(labels.shape, bool)
    mask[tuple(ijk[eligible].T)] = True
    domain = SourceDomain(mask, chain.voxel_to_surface_m)
    positions = domain.centers()
    selected = farthest(positions, 128)
    candidates = positions[selected]
    rng = np.random.default_rng(32042)
    pool = np.flatnonzero(cKDTree(candidates).query(positions)[0] >= 0.001)
    truth = positions[rng.choice(pool, 12, replace=False)]
    mom = rng.normal(size=(12, 3))
    mom *= 1e-8 / np.linalg.norm(mom, axis=1)[:, None]
    combined = np.vstack([candidates, truth])
    if (
        not contains(meshes[3][0], combined).all()
        or distance_to_surface(Points(combined, Frame.MRI), meshes[3][0]).min() < 0.005 - 1e-10
    ):
        raise ValueError("Explicit source containment/margin failed before forward gate")
    np.savez_compressed(
        local / "sources.npz",
        sources_m=combined,
        moments_Am=mom,
        domain_mask=mask,
        voxel_to_mri_m=chain.voxel_to_surface_m,
    )
    native = stages[3]
    checks = {
        k: True
        for k in [
            "topology",
            "nesting",
            "self_intersections",
            "coordinates",
            "sources",
            "materials",
        ]
    }
    checks["electrodes"] = native["sensor_gate_pass"]
    readiness = classify_anatomy(checks, MRI_derived=True, local_permission=True)
    public.update(
        anatomy_status=readiness["status"],
        readiness=readiness,
        geometry=geometry,
        source_coverage={
            "grid_counts": [64, 128],
            "truth_sources": 12,
            "full_GM_voxels": int(gm.sum()),
            "eligible_GM_voxels": int(mask.sum()),
            "eligible_fraction": float(mask.sum() / gm.sum()),
            "definition": (
                "automated MRI GM inside conservative inner-skull inscribed region; "
                "not full cortical coverage"
            ),
            "weights": "actual eligible GM voxel measure, not spherical weights",
        },
        model="three-compartment BEM, brain/CSF homogenized",
        segmentation_evidence=(
            "provided automated FreeSurfer GM labels, not independent anatomical reference"
        ),
        full_conductor_accuracy_established=False,
    )
    if not readiness["forward_allowed"]:
        public.update(failures=failures, forward_executed=False)
        finish(public, local, start)
        return
    require_forward_ready(readiness)
    fields = {}
    forward = []
    for level, solver in [(2, "mne"), (3, "mne"), (4, "mne"), (3, "openmeeg")]:
        try:
            target = local / f"forward-{level}-{solver}"
            receipt = execute(target, level, solver)
            fields[level, solver] = np.loadtxt(target / "lead-V_per_Am.csv", delimiter=",")
            forward.append(
                {
                    k: receipt[k]
                    for k in [
                        "level",
                        "solver",
                        "source_count",
                        "lead_rank",
                        "lead_nonnull_condition",
                        "source_margin_min_mm",
                        "reference_mean_max_V_per_Am",
                        "source_head_pairing_max_m",
                        "seconds",
                        "peak_MiB",
                        "solver_residual",
                    ]
                }
            )
        except (RuntimeError, subprocess.SubprocessError) as exc:
            failures.append(
                dict(
                    dataset="mne-sample",
                    stage=f"forward-{level}-{solver}",
                    error=type(exc).__name__,
                )
            )
        print("Forward", level, solver, "complete", flush=True)
    comparisons = []
    for a, b, name in [
        ((2, "mne"), (3, "mne"), "refinement2to3"),
        ((3, "mne"), (4, "mne"), "refinement3to4"),
        ((3, "mne"), (3, "openmeeg"), "matched_BEM_MNE_OpenMEEG"),
    ]:
        if a in fields and b in fields:
            diff = float(np.linalg.norm(fields[a] - fields[b]) / np.linalg.norm(fields[b]))
            comparisons.append(
                dict(
                    comparison=name,
                    relative=diff,
                    target=0.1,
                    passed=diff <= 0.1,
                    anatomical_accuracy=False,
                )
            )
    inverse = []
    if (4, "mne") in fields and (3, "mne") in fields:
        fine = fields[4, "mne"][:, 384:]
        clean = np.einsum("ijk,jk->ij", fine.reshape(-1, 12, 3), mom)
        n = len(clean)
        proj = average_projector(n)
        noise = NoiseModel((5e-8) ** 2 * proj, tuple(f"E{i:03}" for i in range(n)), proj)
        rn = np.random.default_rng(32043)
        y = clean + 5e-8 * proj @ rn.normal(size=clean.shape)
        for count in [64, 128]:
            grid = candidates[:count]
            prior = SourcePrior.create(grid, "cell_volume", domain=domain)
            g = fields[3, "mne"][:, : 3 * count]
            distance = np.linalg.norm(grid[:, None] - truth[None], axis=2) * 1000
            for method in ["Tikhonov", "MNE", "dSPM"]:
                inv = PriorInverse(g, grid, prior, noise, method)
                alpha = (
                    0.001 * np.linalg.eigvalsh(inv.components()[2])[-1]
                    if method == "Tikhonov"
                    else 1 / 9
                )
                k = inv.kernel(float(alpha))
                for std, yy in [(0.0, clean), (5e-8, y)]:
                    estimate = np.linalg.norm((k @ yy).reshape(count, 3, 12), axis=1)
                    peak = estimate.argmax(axis=0)
                    for s in range(12):
                        inverse.append(
                            dict(
                                candidates=count,
                                method=method,
                                noise_V=std,
                                localization_mm=float(distance[peak[s], s]),
                                nearest_mm=float(distance[:, s].min()),
                                excess_mm=float(distance[peak[s], s] - distance[:, s].min()),
                                dispersion_mm=float(
                                    np.sqrt(
                                        (estimate[:, s] ** 2)
                                        @ distance[:, s] ** 2
                                        / (estimate[:, s] ** 2).sum()
                                    )
                                ),
                                units="dimensionless" if method == "dSPM" else "A*m",
                            )
                        )
    # Only source-averaged numerical summaries; no source/electrode coordinates or fields.
    public.update(
        forward_executed=bool(forward),
        forward=forward,
        comparisons=comparisons,
        inverse_summary=pd.DataFrame(inverse)
        .groupby(["candidates", "method", "noise_V"])
        .mean(numeric_only=True)
        .reset_index()
        .to_dict("records")
        if inverse
        else [],
        inverse_sources=12 if inverse else 0,
        mesh_quality=[
            dict(
                level=k,
                passed=v["surface_geometry_pass"],
                boundaries=[
                    {
                        key: q[key]
                        for key in [
                            "vertex_count",
                            "face_count",
                            "boundary_edges",
                            "nonmanifold_edges",
                            "nonmanifold_vertices",
                            "degenerate_triangles",
                            "connected_components",
                            "triangle_quality_min",
                        ]
                    }
                    for q in v["surface_checks"]["quality"]
                ],
            )
            for k, v in stages.items()
        ],
        electrode_QC={
            k: native[k]
            for k in [
                "EEG_channels",
                "electrode_scalp_max_mm",
                "electrode_scalp_RMS_mm",
                "sensor_inside_scalp_count",
            ]
        },
        failures=failures,
        FEM=(
            "NOT_COMPARABLE: validated four-material FEM and three-compartment human BEM "
            "do not define identical physical inputs"
        ),
    )
    finish(public, local, start)


def finish(public, local, start):
    public.setdefault("full_conductor_accuracy_established", False)
    public.update(
        schema="soma.mri-head-model.aggregate/1",
        design_sha256=DESIGN_SHA,
        human_MRI_used=True,
        human_localization_accuracy=False,
        private_viewer_required=True,
        raw_assets_redistributed=False,
        seconds=time.perf_counter() - start,
        peak_process_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
    )
    (local / "public-summary.json").write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    print("Human MRI workflow complete; public aggregate ready for review", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--local-output", type=Path, required=True)
    a = p.parse_args()
    run(a.local_output)
