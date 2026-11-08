"""External conductor diagnostics and validated synthetic physical controls."""

from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import label

from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.surfaces import ConductorSurfaces
from soma.benchmarks.offgrid import _bem, evaluate_forward, source_grid
from soma.core.provenance import write_json
from soma.datasets.external_anatomy import inspect_sci, read_nrrd
from soma.validation.config import configuration


def require_bem_materials(
    representation: str, boundary_ids: list[int], frame_verified: bool
) -> None:
    if (
        representation != "three-layer triangular BEM"
        or boundary_ids != [1, 3, 4]
        or not frame_verified
    ):
        raise ValueError(
            "Verified triangular inner-skull/outer-skull/scalp boundaries required; FEM is not BEM"
        )


def compare_conductors(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    root = Path(cfg["reference_root"]) / "sci-head"
    with report.stage("external_inventory_and_connectivity"):
        external = inspect_sci(root)
        path = root / "Segmentation/HeadSegmentation.nrrd"
        connectivity = []
        arrays = {}
        if path.exists():
            values, h = read_nrrd(path)
            codes = np.unique(values)
            for code in codes:
                mask = values == code
                _, count = label(mask)
                connectivity.append(
                    {
                        "label_ID": int(code),
                        "name": "unverified ontology ID",
                        "voxel_count": int(mask.sum()),
                        "components_6connected": int(count),
                        "physical_surface_metrics": None,
                        "reason": "anatomical frame/units unresolved; no physical boundary claim",
                    }
                )
            mid = values.shape[2] // 2
            arrays["native_segmentation_slice"] = values[:, :, mid]
            arrays["slice_axis_index"] = np.array([2, mid])
            t1 = root / "T1/T1_Corrected.nrrd"
            if t1.exists():
                image, _ = read_nrrd(t1)
                arrays["native_T1_slice"] = image[:, :, image.shape[2] // 2]
    with report.stage("synthetic_mesh_validation"):
        bem = _bem((0.08, 0.085, 0.09), (0.3, 0.006, 0.3), 2)
        surfaces = ConductorSurfaces.from_mne(
            "synthetic-sphere",
            bem["surfs"],
            {"source": "analytically known nested spheres; no external anatomical claim"},
        )
        readiness = surfaces.readiness(sensor_compatible=True, anatomical_evidence=True)
        arrays["synthetic_radii_m"] = np.array([0.08, 0.085, 0.09])
        for i, mesh in enumerate(surfaces.meshes):
            arrays[f"shell_{i}_vertices_MRI_m"] = mesh.vertices.xyz
            arrays[f"shell_{i}_faces"] = mesh.faces
    with report.stage("physical_forward_recomputation"):
        grid = source_grid(0.01)
        baseline, r = evaluate_forward(grid, kind="BEM")
        receipts = {"baseline": r}
        sensitivity = {}
        arrays["source_grid_MRI_m"] = grid.xyz
        arrays["baseline_lead_V_per_Am"] = baseline
        for name, kwargs in [
            ("boundary_1mm", {"radii": (0.081, 0.085, 0.09)}),
            ("skull_half", {"sigmas": (0.3, 0.003, 0.3)}),
        ]:
            physical: dict[str, Any] = dict(kwargs)
            test, receipt = evaluate_forward(grid, kind="BEM", **physical)
            receipts[name] = receipt
            relative = np.linalg.norm(
                (test - baseline).reshape(24, -1, 3), axis=(0, 2)
            ) / np.linalg.norm(baseline.reshape(24, -1, 3), axis=(0, 2))
            arrays[name + "_lead_V_per_Am"] = test
            arrays[name + "_relative_per_source"] = relative
            sensitivity[name] = {
                "relative_lead_Frobenius": float(
                    np.linalg.norm(test - baseline) / np.linalg.norm(baseline)
                ),
                "per_source_range": [float(relative.min()), float(relative.max())],
                "singular_values": np.linalg.svd(test, compute_uv=False).tolist(),
            }
    summary = {
        "status": "external_inventory_complete_BEM_indeterminate",
        "external": external,
        "external_label_connectivity": connectivity,
        "external_BEM_sensitivity_status": (
            "blocked: unverified anatomical frame/ontology/interfaces"
        ),
        "synthetic_control_readiness": readiness,
        "synthetic_sensitivity": sensitivity,
        "forward_receipts": receipts,
        "external_FEM_converted": False,
        "boundary_difference_status": (
            "external correspondence unavailable; synthetic +1mm known displacement"
        ),
        "anatomical_generalization_claimed": False,
    }
    write_json(output / "external-reference.json", external)
    np.savez_compressed(output / "conductor-arrays.npz", **arrays)
    from soma.validation.plots import conductor_plots

    conductor_plots(output, summary, arrays)
    return report.finish(summary)
