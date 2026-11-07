"""Deterministic physical MRI experiments, independent truth and real anatomy."""

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from soma.core.provenance import sha256, write_json
from soma.datasets.structural import cached_structural, fetch_structural
from soma.imaging.mesh_quality import mesh_quality, nested_boundaries
from soma.imaging.nifti import load_nifti, save_nifti
from soma.imaging.phantoms import (
    LANDMARKS_M,
    analytic_sphere_field,
    asymmetric,
    ellipsoid,
    grid,
    known_transform,
    sphere,
    transformed_asymmetric,
)
from soma.imaging.registration import RegistrationConfig, register
from soma.imaging.reporting import ImagingReport
from soma.imaging.resampling import resample
from soma.imaging.segmentation import agreement, process_mask, region_volumes, threshold_mask
from soma.imaging.surfaces import Mesh, extract_surface, isosurface
from soma.imaging.validation import transform_error, validate_volume
from soma.imaging.volumes import Volume


def configuration(path: Path = Path("configs/mri-geometry.yaml")) -> dict[str, Any]:
    return {
        **dict(yaml.safe_load(path.read_text())),
        "_configuration_file_sha256": sha256(path),
        "_configuration_path": str(path),
    }


def registration_config(config: dict[str, Any], mode: str = "rigid") -> RegistrationConfig:
    parameters = dict(config["registration"])
    parameters["mode"] = mode
    parameters["shrink_factors"] = tuple(parameters["shrink_factors"])
    parameters["smoothing_sigmas_mm"] = tuple(parameters["smoothing_sigmas_mm"])
    return RegistrationConfig(**parameters)


def target_grid(source: Volume, spacing_m: float) -> Volume:
    # Preserve physical first center and storage orientation; target covers the
    # native center-to-center extent. Shear is explicitly rejected by SITK later.
    a = source.affine_m.copy()
    a[:3, :3] = a[:3, :3] / source.spacing_m * spacing_m
    shape = tuple(
        int(np.ceil((n - 1) * spacing / spacing_m)) + 1
        for n, spacing in zip(source.shape, source.spacing_m, strict=True)
    )
    return Volume(np.zeros(shape, dtype=np.float32), a)


def _save_mesh(path: Path, mesh: Mesh) -> None:
    np.savez_compressed(path, vertices_RAS_m=mesh.vertices.xyz, triangles=mesh.faces)


def synthetic_experiment(
    output: Path, *, seed: int = 42, config_path: Path = Path("configs/mri-geometry.yaml")
) -> dict[str, Any]:
    config = configuration(config_path)
    config["seed"] = seed
    report = ImagingReport(output, config, seed=seed, source={"origin": "mathematical phantoms"})
    fixed = asymmetric(tuple(config["synthetic"]["spacing_m"]), seed=seed)
    save_nifti(fixed, output / "asymmetric-phantom.nii.gz")
    records, example = [], None
    for mode in ("rigid", "affine"):
        for magnitude in config["synthetic"]["perturbation_multipliers"]:
            truth = known_transform(mode, magnitude)
            moving = transformed_asymmetric(fixed, truth)
            result = register(fixed, moving, registration_config(config, mode))
            warped = result.warp(moving, fixed, allow_repeated=True)
            errors = transform_error(result.transform, truth, LANDMARKS_M)
            before = float(np.mean((moving.array() - fixed.array()) ** 2))
            after = float(np.mean((warped.array() - fixed.array()) ** 2))
            reverse = (
                register(moving, fixed, registration_config(config, mode))
                if magnitude == 1
                else None
            )
            independent_inverse_m = None
            if reverse is not None:
                chain = reverse.transform.matrix @ result.transform.matrix
                independent_inverse_m = float(
                    np.max(
                        np.linalg.norm(
                            LANDMARKS_M @ chain[:3, :3].T + chain[:3, 3] - LANDMARKS_M, axis=1
                        )
                    )
                )
            accepted = (
                errors["median_landmark_TRE_m"]
                < config["acceptance"][f"{mode}_median_landmark_TRE_m"]
                and errors["rotation_error_deg"] < config["acceptance"]["rotation_error_deg"]
            )
            masks_compare = [
                Volume((v.array() > 0.2).astype(np.uint8), v.affine_m, "labels")
                for v in (fixed, moving, warped)
            ]
            overlap_before = agreement(masks_compare[0], masks_compare[1])["dice"]
            overlap_after = agreement(masks_compare[0], masks_compare[2])["dice"]
            records.append(
                {
                    "mode": mode,
                    "perturbation_multiplier": magnitude,
                    **errors,
                    "physical_grid_Dice_before": overlap_before,
                    "physical_grid_Dice_after": overlap_after,
                    "before_MSE": before,
                    "after_MSE": after,
                    "independent_reverse_consistency_m": independent_inverse_m,
                    "accepted_landmarks": bool(accepted),
                    "runtime_s": result.diagnostics["runtime_s"],
                }
            )
            result.save(output / f"registration-{mode}-{magnitude}")
            write_json(
                output / f"truth-{mode}-{magnitude}.json",
                {
                    "fixed_to_moving_RAS_m": truth.matrix.tolist(),
                    "landmarks_fixed_RAS_m": LANDMARKS_M.tolist(),
                },
            )
            if mode == "rigid" and magnitude == 1:
                example = (fixed, moving, warped)
    pd.DataFrame(records).to_csv(output / "registration-errors.csv", index=False)
    # Explicit failures: constant data is rejected; sphere rotation is ambiguous.
    failures = []
    for name, phantom, magnitude in (
        ("constant", grid(), 1),
        ("minimal_overlap", fixed, 12),
        (
            "rotationally_ambiguous_sphere",
            Volume(sphere(0.025, 0.004).array().astype(np.float32), sphere(0.025, 0.004).affine_m),
            1,
        ),
    ):
        truth = known_transform("rigid", magnitude)
        moving = resample(phantom, phantom, reference_to_source=truth.inverse())
        try:
            estimated = register(
                phantom,
                moving,
                replace(registration_config(config), iterations=60, initialization="identity"),
            )
            metrics = transform_error(estimated.transform, truth, LANDMARKS_M)
            failures.append(
                {
                    "case": name,
                    "numerically_completed": True,
                    "anatomically_accepted": False,
                    "known_failure_or_ambiguity": True,
                    **metrics,
                    "stop": estimated.diagnostics["optimizer_stop"],
                }
            )
        except ValueError as exc:
            failures.append(
                {
                    "case": name,
                    "numerically_completed": False,
                    "anatomically_accepted": False,
                    "reason": str(exc),
                }
            )
    write_json(output / "failure-cases.json", failures)
    surface_rows = []
    for spacing in config["synthetic"]["surface_spacing_m"]:
        for name, mask in (
            ("sphere", sphere(config["synthetic"]["sphere_radius_m"], spacing)),
            ("ellipsoid", ellipsoid(spacing)),
        ):
            started = time.perf_counter()
            mesh = extract_surface(mask)
            extract_seconds = time.perf_counter() - started
            quality = mesh_quality(mesh)
            radius = config["synthetic"]["sphere_radius_m"]
            exact_volume = (
                4 * np.pi / 3 * (radius**3 if name == "sphere" else 0.035 * 0.025 * 0.018)
            )
            exact_area = 4 * np.pi * radius**2 if name == "sphere" else None
            # Ellipsoid volume is exact; its commonly used p-formula area is only
            # approximate, so do not use it as an exact surface-area oracle.
            surface_rows.append(
                {
                    "kind": name,
                    "spacing_m": spacing,
                    "mesh_area_m2": quality["surface_area_m2"],
                    "mesh_volume_m3": quality["enclosed_volume_m3"],
                    "volume_relative_error": abs(quality["signed_volume_m3"] - exact_volume)
                    / exact_volume,
                    "area_relative_error": abs(quality["surface_area_m2"] - exact_area) / exact_area
                    if exact_area
                    else None,
                    "euler": quality["euler_characteristic"],
                    "valid": quality["geometrically_valid_under_checks"],
                    "extraction_s": extract_seconds,
                }
            )
    for spacing in config["synthetic"]["surface_spacing_m"]:
        radius = config["synthetic"]["sphere_radius_m"]
        mesh = isosurface(analytic_sphere_field(spacing, radius), level=0)
        q = mesh_quality(mesh)
        surface_rows.append(
            {
                "kind": "analytic_sphere_field",
                "spacing_m": spacing,
                "mesh_area_m2": q["surface_area_m2"],
                "mesh_volume_m3": q["enclosed_volume_m3"],
                "volume_relative_error": abs(q["signed_volume_m3"] - 4 * np.pi / 3 * radius**3)
                / (4 * np.pi / 3 * radius**3),
                "area_relative_error": abs(q["surface_area_m2"] - 4 * np.pi * radius**2)
                / (4 * np.pi * radius**2),
                "euler": q["euler_characteristic"],
                "valid": q["geometrically_valid_under_checks"],
            }
        )
    pd.DataFrame(surface_rows).to_csv(output / "surface-convergence.csv", index=False)
    masks = [
        sphere(radius, config["synthetic"]["nested_spacing_m"])
        for radius in config["synthetic"]["nested_radii_m"]
    ]
    meshes = [extract_surface(mask) for mask in masks]
    nesting = nested_boundaries(
        meshes, minimum_separation_m=config["acceptance"]["nested_minimum_separation_m"]
    )
    write_json(output / "nested-boundaries.json", nesting)
    for index, mesh in enumerate(meshes):
        _save_mesh(output / f"nested-boundary-{index}.npz", mesh)
    tissue = masks[2].array() + masks[1].array() + masks[0].array()
    labels = Volume(
        tissue.astype(np.uint8), masks[0].affine_m, "labels", {"origin": "synthetic_tissue_levels"}
    )
    noisy = Volume(
        tissue.astype(np.float32)
        + np.random.default_rng(seed).normal(0, 0.1, tissue.shape).astype(np.float32),
        labels.affine_m,
    )
    baseline = threshold_mask(noisy, threshold=1.5)
    target = Volume((tissue >= 2).astype(np.uint8), labels.affine_m, "labels")
    segmentation = agreement(baseline, target)
    save_nifti(labels, output / "synthetic-tissue-labels.nii.gz")
    write_json(
        output / "segmentation.json",
        {
            **segmentation,
            "truth": "synthetic levels >=2; not GM/WM/CSF anatomy",
            "baseline_metadata": baseline.metadata,
            "intensity_noise_std": 0.1,
            "seed": seed,
            "region_volumes_m3": region_volumes(labels),
        },
    )
    from soma.visualization.mri import synthetic_figures

    assert example is not None
    synthetic_figures(output, *example, pd.DataFrame(records), meshes, nesting)
    return report.finish(
        {
            "status": "complete",
            "registration": records,
            "failure_cases": failures,
            "surface_convergence": surface_rows,
            "nested_geometric_candidate": nesting["geometric_candidate"],
            "segmentation": segmentation,
            "geometry": validate_volume(fixed),
            "all_small_perturbation_landmark_acceptance": all(
                r["accepted_landmarks"] for r in records
            ),
        }
    )


def real_experiment(
    output: Path,
    *,
    fetch: bool = False,
    dataset: str = "spm-auditory",
    config_path: Path = Path("configs/mri-geometry.yaml"),
) -> dict[str, Any]:
    if dataset != "spm-auditory":
        raise ValueError("Supported structural dataset: spm-auditory")
    config = configuration(config_path)
    root = Path(config["real"]["root"])
    path, source = fetch_structural(root) if fetch else cached_structural(root)
    report = ImagingReport(output, config, seed=config["seed"], source=source)
    started = time.perf_counter()
    native = load_nifti(path)
    load_seconds = time.perf_counter() - started
    inspection = validate_volume(native, check_data=True)
    write_json(output / "nifti-inspection.json", inspection)
    started = time.perf_counter()
    fixed = resample(native, target_grid(native, config["real"]["target_spacing_m"]))
    resample_seconds = time.perf_counter() - started
    truth = known_transform("rigid")
    moving = resample(fixed, fixed, reference_to_source=truth.inverse(), allow_repeated=True)
    result = register(fixed, moving, registration_config(config))
    warped = result.warp(moving, fixed, allow_repeated=True)
    result.save(output / "controlled-registration")
    # Independent physical probes in the actual MRI FOV, not invented anatomical landmarks.
    center = fixed.grid.to_world(np.array([(np.array(fixed.shape) - 1) / 2])).xyz[0]
    probes = center + LANDMARKS_M
    errors = transform_error(result.transform, truth, probes)
    write_json(
        output / "controlled-registration-truth.json",
        {
            "fixed_to_moving_RAS_m": truth.matrix.tolist(),
            "physical_test_points_RAS_m": probes.tolist(),
            "anatomical_landmarks": False,
        },
    )
    # This is a coarse foreground/head envelope, never a claimed brain/tissue mask.
    foreground = threshold_mask(native)
    mask = resample(foreground, target_grid(native, config["real"]["surface_spacing_m"]), order=0)
    mask = process_mask(mask, closing_iterations=1, fill_holes=True, largest_component=True)
    save_nifti(mask, output / "estimated-foreground-mask.nii.gz")
    started = time.perf_counter()
    mesh = extract_surface(mask)
    extraction_seconds = time.perf_counter() - started
    started = time.perf_counter()
    quality = mesh_quality(mesh)
    quality_seconds = time.perf_counter() - started
    _save_mesh(output / "estimated-foreground-surface.npz", mesh)
    write_json(output / "mesh-quality.json", quality)
    for name, volume in (
        ("reference-3mm", fixed),
        ("controlled-moving", moving),
        ("controlled-recovered", warped),
    ):
        save_nifti(volume, output / f"{name}.nii.gz")
    from soma.visualization.mri import real_figures

    real_figures(output, native, fixed, moving, warped, mask, mesh, quality)
    return report.finish(
        {
            "status": "complete",
            "source": source,
            "native_geometry": native.geometry(),
            "metadata": native.metadata,
            "load_s": load_seconds,
            "resample_s": resample_seconds,
            "registration": {**errors, **result.diagnostics},
            "surface_extraction_s": extraction_seconds,
            "mesh_validation_s": quality_seconds,
            "mesh": {k: v for k, v in quality.items() if k != "triangle_quality"},
            "mask_interpretation": (
                "coarse Otsu foreground/head envelope, not validated brain or tissue segmentation"
            ),
            "estimated_mask_metadata": mask.metadata,
            "surface_metadata": mesh.metadata,
            "reference_segmentation_available": False,
            "BEM_candidate": False,
            "individual_EEG_alignment_available": False,
        }
    )
