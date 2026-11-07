"""Optional MRI profiling, including isolated lazy/eager process memory."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from soma.imaging.mesh_quality import mesh_quality
from soma.imaging.nifti import load_nifti
from soma.imaging.phantoms import LANDMARKS_M, asymmetric, known_transform, transformed_asymmetric
from soma.imaging.registration import register
from soma.imaging.reporting import ImagingReport
from soma.imaging.resampling import resample
from soma.imaging.segmentation import process_mask, threshold_mask
from soma.imaging.surfaces import extract_surface


def benchmark(input_path: Path, output: Path) -> dict[str, Any]:
    report = ImagingReport(
        output, {"input": str(input_path), "threads": 1}, source={"MRI": str(input_path)}
    )
    script = """import json,resource,sys,time
from pathlib import Path
from soma.imaging.nifti import load_nifti
start=time.perf_counter();v=load_nifti(Path(sys.argv[1]));load=time.perf_counter()-start
before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
units=1024**2 if sys.platform=='darwin' else 1024
start=time.perf_counter();size=v.array().nbytes if sys.argv[2]=='eager' else 0
print(json.dumps({
'mode':sys.argv[2],
'load_s':load,
'materialize_s':time.perf_counter()-start,
'peak_RSS_MiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/units,

'peak_delta_MiB':(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-before)/units,

'materialized_bytes':size,
'stored_voxel_bytes':int(__import__('numpy').prod(v.shape))*v.dtype.itemsize}))"""
    profiles = []
    for mode in ("lazy", "eager"):
        profile_process = subprocess.run(
            [sys.executable, "-c", script, str(input_path), mode],
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=True,
        )
        profiles.append(json.loads(profile_process.stdout))
    v = load_nifti(input_path)
    report.source = v.metadata
    from soma.experiments.mri_geometry import target_grid

    started = time.perf_counter()
    low = resample(v, target_grid(v, 0.005))
    resample_s = time.perf_counter() - started
    points = np.random.default_rng(42).uniform(0, np.array(v.shape), (100000, 3))
    started = time.perf_counter()
    world = v.grid.to_world(points)
    transformed = v.grid.to_voxel(world)
    point_s = time.perf_counter() - started
    mask = process_mask(
        threshold_mask(low), closing_iterations=1, fill_holes=True, largest_component=True
    )
    started = time.perf_counter()
    surface = extract_surface(mask)
    extract_s = time.perf_counter() - started
    started = time.perf_counter()
    quality = mesh_quality(surface)
    mesh_s = time.perf_counter() - started
    f = asymmetric()
    m = transformed_asymmetric(f, known_transform())
    started = time.perf_counter()
    result = register(f, m)
    registration_s = time.perf_counter() - started
    return report.finish(
        {
            "status": "complete",
            "isolated_loading_profiles": profiles,
            "resample_s": resample_s,
            "points": len(points),
            "point_roundtrip_s": point_s,
            "roundtrip_max_voxel_error": float(np.max(np.abs(transformed - points))),
            "surface_extraction_s": extract_s,
            "mesh_validation_s": mesh_s,
            "mesh_faces": quality["face_count"],
            "registration_s": registration_s,
            "registration_optimizer": result.diagnostics["optimizer_stop"],
            "landmarks_m": LANDMARKS_M.tolist(),
        }
    )
