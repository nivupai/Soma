"""Controlled synthetic references; tolerances express math, never clinical validity."""

import hashlib
import importlib.metadata
import json
import platform
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import welch as scipy_welch
from scipy.spatial.distance import cdist
from threadpoolctl import threadpool_info

from soma.sdk.eeg import EpochSet, MorletConfig, Signal, WelchConfig, morlet_power, welch
from soma.sdk.fmri import Contrast, ModelConfig, contrast, fit
from soma.sdk.imaging import (
    Frame,
    LabelVolume,
    Mesh,
    Points,
    Transform,
    Volume,
    mesh_quality,
    ras_lps,
    resample_labels,
    score,
)
from soma.sdk.provenance import array_fingerprint
from soma.sdk.results import (
    create_result,
    load_result,
    migrate_legacy,
    save_result,
    verify_integrity,
)
from soma.sdk.source import Tikhonov
from soma.sdk.synthetic import simulate_fmri


def run_suite() -> dict[str, Any]:
    """Twelve cases with independently specified references and actual error values."""
    cases = []
    protocol_bytes = (
        files("soma.resources").joinpath("reproducibility-tolerances-v1.json").read_bytes()
    )
    tolerances = json.loads(protocol_bytes)

    def check(
        name: str, actual: Any, reference: Any, *, atol: float, rtol: float, rationale: str
    ) -> None:
        if tolerances[name] != {"atol": atol, "rtol": rtol}:
            raise ValueError("Benchmark tolerances differ from the frozen v1 protocol")
        a, b = np.asarray(actual, dtype=float), np.asarray(reference, dtype=float)
        error = float(np.max(np.abs(a - b)))
        scale = float(np.max(np.abs(b)))
        passed = bool(np.allclose(a, b, atol=atol, rtol=rtol))
        cases.append(
            {
                "case": name,
                "max_absolute_error": error,
                "relative_error": error / max(scale, 1e-300),
                "atol": atol,
                "rtol": rtol,
                "reference_scale": scale,
                "actual_values": a.tolist(),
                "reference_values": b.tolist(),
                "passed": passed,
                "rationale": rationale,
            }
        )
        if not passed:
            raise ValueError("Numerical reproducibility case failed: " + name)

    affine = np.array(
        [[0.002, 0, 0, -0.01], [0, 0.003, 0, 0.02], [0, 0, 0.004, -0.03], [0, 0, 0, 1.0]]
    )
    volume = Volume(np.zeros((8, 9, 10)), affine)
    indices = np.array([[0.0, 0, 0], [2, 3, 4], [7, 8, 9]])
    expected = np.column_stack(
        (0.002 * indices[:, 0] - 0.01, 0.003 * indices[:, 1] + 0.02, 0.004 * indices[:, 2] - 0.03)
    )
    check(
        "voxel_world",
        volume.grid.to_world(indices).xyz,
        expected,
        atol=2e-16,
        rtol=2e-14,
        rationale="well-conditioned diagonal affine; ~100 epsilon absolute margin in metres",
    )
    points = Points(expected, Frame.RAS)
    check(
        "RAS_LPS",
        ras_lps().apply(points).xyz,
        expected * np.array([-1, -1, 1]),
        atol=0,
        rtol=0,
        rationale="exact sign flips, no interpolation",
    )
    labels = np.zeros((8, 9, 10), np.uint8)
    labels[2:5, 2:5, 2:5] = 1
    mask = Volume(labels, affine, "labels")
    check(
        "nearest_labels",
        resample_labels(
            mask, mask, reference_to_source=Transform(Frame.RAS, Frame.RAS, np.eye(4))
        ).array(),
        labels,
        atol=0,
        rtol=0,
        rationale="integer nearest identity is exact",
    )
    shifted = np.zeros_like(labels)
    shifted[3:6, 2:5, 2:5] = 1
    p = LabelVolume(
        Volume(shifted, affine, "labels"),
        "synthetic",
        "native",
        {1: "cube"},
        {"source": "translated independent cube"},
    )
    r = LabelVolume(mask, "synthetic", "native", {1: "cube"}, {"source": "analytic cube"})
    metrics = score(p, r)["labels"][0]

    # Two 3³ cubes overlap 2×3×3 voxels. Independent brute-force physical faces.
    def faces(data: Any) -> tuple[Any, Any]:
        pts = []
        areas = []
        for x, y, z in np.argwhere(data):
            cell = np.array([x, y, z], float)
            for axis in range(3):
                for sign in [-1, 1]:
                    neighbor = cell.astype(int)
                    neighbor[axis] += sign
                    if (
                        not np.all((neighbor >= 0) & (neighbor < np.array(data.shape)))
                        or not data[tuple(neighbor)]
                    ):
                        center = cell.copy()
                        center[axis] += sign * 0.5
                        pts.append((affine[:3, :3] @ center + affine[:3, 3]) * 1000)
                        other = [i for i in range(3) if i != axis]
                        areas.append(np.prod(np.diag(affine)[other]) * 1e6)
        return np.array(pts), np.array(areas)

    pp, pa = faces(shifted)
    rr, ra = faces(labels)
    distance = cdist(pp, rr)
    oracle = (distance.min(axis=1) @ pa + distance.min(axis=0) @ ra) / (pa.sum() + ra.sum())
    check(
        "segmentation",
        [metrics["Dice"], metrics["Jaccard"], metrics["ASSD_mm"]],
        [2 * 18 / 54, 18 / 36, oracle],
        atol=1e-12,
        rtol=1e-12,
        rationale="analytic overlap plus all-pairs distances, independent of KD-tree scorer",
    )
    tetra = Mesh(
        Points(np.array([[0.0, 0, 0], [0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]]), Frame.RAS),
        np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]),
    )
    q = mesh_quality(tetra)
    check(
        "surface_geometry",
        [q["surface_area_m2"], q["enclosed_volume_m3"]],
        [(3 + np.sqrt(3)) * 0.0001 / 2, 1e-6 / 6],
        atol=1e-18,
        rtol=1e-12,
        rationale="closed tetrahedron determinant and equilateral-face area",
    )
    values = 4e-6 * np.sin(2 * np.pi * 10 * np.arange(1600) / 160)
    spec = welch(Signal(values, 160), WelchConfig())
    f, d = scipy_welch(
        values,
        fs=160,
        nperseg=320,
        noverlap=160,
        window="hann",
        detrend="constant",
        scaling="density",
    )
    check(
        "Welch_density",
        spec.density,
        d,
        atol=1e-25,
        rtol=1e-11,
        rationale="independent SciPy Welch call, V²/Hz roundoff scale",
    )
    check(
        "spectral_integral",
        spec.band_power(8, 13),
        8e-12,
        atol=1e-24,
        rtol=1e-10,
        rationale="pure-tone variance A²/2, bin-centered Hann leakage retained inside band",
    )
    epoch = EpochSet(values[None, None, :], ("synthetic",), 160, np.arange(1600) / 160, (), ())
    tf = morlet_power(epoch, MorletConfig((10.0,), 5.0))
    observed = float(np.nanmean(tf.power[..., tf.valid[0]]))
    sigma = 5 / (2 * np.pi * 10)
    expected_power = (4e-6) ** 2 * 160 * sigma * np.sqrt(np.pi)
    check(
        "Morlet_summary",
        observed,
        expected_power,
        atol=1e-18,
        rtol=2e-4,
        rationale=(
            "analytic sinusoid/Gaussian response; finite five-sigma truncation "
            "and zero-mean correction dominate epsilon"
        ),
    )
    inverse = Tikhonov(np.eye(3), 0.1)
    check(
        "source_inverse",
        inverse.solve(np.array([1.0, 2, 3])),
        np.array([1.0, 2, 3]) / 1.1,
        atol=1e-14,
        rtol=1e-13,
        rationale="closed-form diagonal Tikhonov shrinkage",
    )
    run, _ = simulate_fmri(seed=17042)
    fitted = fit(
        run, ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    )
    estimate = contrast(fitted, Contrast("task", {"task": 1.0}))
    x = fitted.design.to_numpy()
    y = np.asarray(run.image.dataobj).reshape(-1, run.n_scans).T
    qr, tri = np.linalg.qr(x)
    beta = np.linalg.solve(tri, qr.T @ y)
    c = estimate.contrast.vector(fitted.design)
    effect = c @ beta
    residual = y - x @ beta
    variance = (
        np.sum(residual**2, axis=0) / (len(x) - x.shape[1]) * np.sum(np.linalg.solve(tri.T, c) ** 2)
    )
    check(
        "GLM_effect",
        np.asarray(estimate.maps["effect_size"].dataobj).ravel(),
        effect,
        atol=1e-9,
        rtol=1e-9,
        rationale="independent QR oracle; recorded design condition "
        + str(float(np.linalg.cond(x))),
    )
    check(
        "contrast_variance",
        np.asarray(estimate.maps["effect_variance"].dataobj).ravel(),
        variance,
        atol=1e-10,
        rtol=1e-8,
        rationale="unbiased residual variance times cᵀ(XᵀX)⁻¹c; no human calibration claim",
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = create_result(
            "experiment.manifest",
            {
                "computation": "synthetic serialization oracle",
                "inputs": {},
                "environment": {},
                "assumptions": ["deterministic input"],
                "validation": {},
                "limitations": ["not scientific validity"],
            },
            arrays={"reference": np.arange(16, dtype=np.float64)},
            provenance={"source": "analytic arange"},
            method={"id": "identity", "version": "1"},
            parameters={},
            units={},
            dataset_identity="synthetic",
            subject_identity=None,
            spatial_reference=None,
            temporal_reference=None,
            statistical_estimand=None,
        )
        path = save_result(
            result, {"reference": np.arange(16, dtype=np.float64)}, root / "artifact"
        )
        loaded, arrays = load_result(path)
        verify_integrity(path)
        legacy = root / "legacy.json"
        legacy.write_text('{"schema_version":1,"parameters":{"value":1.25}}')
        upgraded, _, receipt = migrate_legacy(legacy, source_format="core-manifest-v1")
        exact = (
            np.array_equal(arrays["reference"], np.arange(16))
            and upgraded["payload"]["values"] == json.loads(legacy.read_text())
            and receipt["numerical_values_preserved"]
        )
        check(
            "serialization_migration_checksums",
            int(exact),
            1,
            atol=0,
            rtol=0,
            rationale=(
                "exact numerical payload and JSON equality; "
                "file hashes verified within each execution"
            ),
        )
    versions = {
        n: importlib.metadata.version(n)
        for n in [
            "soma-neuro",
            "numpy",
            "scipy",
            "mne",
            "neurodsp",
            "nilearn",
            "nibabel",
            "SimpleITK",
            "scikit-learn",
            "pyriemann",
        ]
    }
    backend = [
        {
            k: v
            for k, v in info.items()
            if k in {"internal_api", "version", "num_threads", "architecture", "threading_layer"}
        }
        for info in threadpool_info()
    ]
    return {
        "benchmark": "soma.synthetic-reproducibility-v1",
        "tolerance_protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "schema_version": "1.0.0",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "dependencies": versions,
        "numerical_backends": backend,
        "cases": cases,
        "all_passed": all(c["passed"] for c in cases),
        "interpretation": (
            "numerical equivalence under stated tolerances; "
            "not statistical/anatomical/clinical validation"
        ),
        "input_hashes": {
            "affine": array_fingerprint(affine),
            "voxel_indices": array_fingerprint(indices),
            "labels": array_fingerprint(labels),
            "EEG_values": array_fingerprint(values),
            "GLM_image": array_fingerprint(np.asarray(run.image.dataobj)),
            "GLM_design": array_fingerprint(x),
            "serialization": hashlib.sha256(np.arange(16, dtype="<f8").tobytes()).hexdigest(),
        },
    }
