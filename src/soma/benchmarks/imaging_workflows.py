"""Independent label benchmarks, analytic convergence and repair audits."""

import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soma.anatomy.reporting import AnatomyReport
from soma.benchmarks.config import configuration
from soma.benchmarks.segmentation import LabelVolume, intensity_baseline, score
from soma.benchmarks.surfaces import convergence_record, field, mask_perturbations, repair_cases
from soma.benchmarks.topology import repair, topology
from soma.core.provenance import sha256, write_json
from soma.datasets.references import DKT31, load_reference, read_cortical_surface
from soma.imaging.nifti import save_nifti
from soma.imaging.resampling import resample
from soma.imaging.surfaces import extract_surface, isosurface
from soma.imaging.volumes import Volume


def segmentation_benchmark(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    root = Path(cfg["reference_root"])
    report = AnatomyReport(output, cfg, seed=cfg["seed"])
    results = {}
    images = {}
    missing = []
    with report.stage("BrainWeb_loading_and_baseline"):
        try:
            image = load_reference(
                root / "brainweb" / (cfg["brainweb_alias"] + ".mnc.gz"),
                kind="intensity",
                subject="brainweb-normal",
                space="BrainWeb-Talairach",
            )
            truth = load_reference(
                root / "brainweb" / (cfg["brainweb_truth"] + ".mnc.gz"),
                kind="labels",
                subject="brainweb-normal",
                space="BrainWeb-Talairach",
            )
            codes, counts = np.unique(truth.array(), return_counts=True)
            official = {
                0: 3001960,
                1: 371945,
                2: 902912,
                3: 674777,
                4: 146514,
                5: 617482,
                6: 726649,
                7: 362561,
                8: 5987,
                9: 298350,
            }
            if dict(zip(codes.tolist(), counts.tolist(), strict=True)) != official:
                raise ValueError(
                    "BrainWeb discrete reference differs from official published class counts"
                )
            prediction = intensity_baseline(image)
            ontology = {1: "CSF", 2: "gray matter", 3: "white matter"}
            with report.stage("BrainWeb_scoring"):
                results["BrainWeb"] = score(
                    LabelVolume(
                        prediction,
                        "brainweb-normal",
                        "BrainWeb-Talairach",
                        ontology,
                        prediction.metadata,
                    ),
                    LabelVolume(
                        truth, "brainweb-normal", "BrainWeb-Talairach", ontology, truth.metadata
                    ),
                    tolerances_mm=tuple(cfg["surface_tolerances_mm"]),
                )
            results["BrainWeb"]["reference_class_counts_verified"] = official
            save_nifti(prediction, output / "brainweb-baseline.nii.gz")
            k = image.shape[0] // 2
            images["BrainWeb"] = {
                "T1": image.array()[k],
                "reference": truth.array()[k],
                "prediction": prediction.array()[k],
            }
        except FileNotFoundError as exc:
            missing.append({"dataset": "BrainWeb", "error": str(exc)})
    with report.stage("Mindboggle_loading_and_alignment"):
        try:
            subject = cfg["mindboggle_subject"]
            base = root / "mindboggle"
            selected = base / "selected/NKI-RS-22_volumes" / subject
            manual_path = selected / "labels.DKT31.manual.nii.gz"
            external_path = base / (subject + ".JTatlas40+aseg.nii.gz")
            image = load_reference(
                selected / "t1weighted.nii.gz",
                kind="intensity",
                subject=subject,
                space=subject + "-native-RAS",
            )
            truth = load_reference(
                manual_path,
                kind="labels",
                subject=subject,
                space=subject + "-native-RAS",
                units_override="mm",
            )
            prediction = load_reference(
                external_path, kind="labels", subject=subject, space=subject + "-native-RAS"
            )
            if sha256(manual_path) == sha256(external_path):
                raise ValueError("Prediction is the reference file; independent evaluation refused")
            if not image.same_grid(truth):
                raise ValueError("Supplied native T1/manual grid mismatch")
            text = (base / "label_definitions.txt").read_text()
            ontology = {}
            for code, name in re.findall(r'\[(\d+),\s*"([^\"]+)"\]', text):
                ontology.setdefault(int(code), name)
            targets = [*DKT31, *[x + 1000 for x in DKT31]]
            ontology = {k: ontology[k] for k in targets}
            alignment = {"registration_performed": False, "supplied_native_world_RAS": True}
            if not prediction.same_grid(truth):
                pull = np.linalg.solve(prediction.affine_m, truth.affine_m)
                if not np.allclose(pull, np.rint(pull), atol=1e-5, rtol=0):
                    raise ValueError(
                        "Supplied world-grid relation is not the expected exact integer "
                        "reindexing/crop"
                    )
                alignment["explicit_nearest_neighbor_pull"] = pull.tolist()
                prediction = resample(prediction, truth, order=0)
            test = (base / "mindboggle101_atlases_testset.txt").read_text().split()
            train = (base / "mindboggle101_atlases_trainset.txt").read_text().split()
            with report.stage("Mindboggle_scoring"):
                results["Mindboggle"] = score(
                    LabelVolume(
                        prediction,
                        subject,
                        subject + "-native-RAS",
                        ontology,
                        {
                            "method": "supplied JTAtlas40 classifier, external prediction",
                            "sha256": sha256(external_path),
                            "alignment": alignment,
                        },
                    ),
                    LabelVolume(
                        truth,
                        subject,
                        subject + "-native-RAS",
                        ontology,
                        {
                            "method": "manual DKT31 cortical parcellation",
                            "sha256": sha256(manual_path),
                            "license": "CC BY 4.0",
                        },
                    ),
                    tolerances_mm=tuple(cfg["surface_tolerances_mm"]),
                )
            results["Mindboggle"].update(
                {
                    "alignment": alignment,
                    "listed_in_testset": subject in test,
                    "listed_in_trainset": subject in train,
                    "classifier_lineage_note": (
                        "JTAtlas40 training scan list is separately retained; test/train "
                        "lists alone do not certify all pipeline independence"
                    ),
                    "cortical_labels_not_tissue_truth": True,
                }
            )
            surface_assets = []
            for surface_path in (base / "surfaces").rglob("*.DKT31.manual.vtk"):
                surface = read_cortical_surface(surface_path, subject)
                np.savez_compressed(
                    output / (surface_path.name + ".npz"),
                    points_as_stored_mm=surface["points_as_stored_mm"],
                    faces=surface["faces"],
                    manual_labels=surface["manual_labels"],
                )
                surface_assets.append(
                    {
                        "path": str(surface_path),
                        "sha256": surface["sha256"],
                        "vertices": len(surface["points_as_stored_mm"]),
                        "faces": len(surface["faces"]),
                        "label_count": len(np.unique(surface["manual_labels"])),
                        "coordinate_frame": surface["coordinate_frame"],
                    }
                )
            results["Mindboggle"]["cortical_surface_assets"] = surface_assets
            k = image.shape[2] // 2
            images["Mindboggle"] = {
                "T1": image.array()[:, :, k],
                "reference": truth.array()[:, :, k],
                "prediction": prediction.array()[:, :, k],
            }
        except FileNotFoundError as exc:
            missing.append({"dataset": "Mindboggle", "error": str(exc)})
    with report.stage("controlled_mask_perturbations"):
        truth, variants = mask_perturbations(cfg["seed"])
        controlled = []
        for name, prediction in variants.items():
            scored = score(
                LabelVolume(
                    prediction, "analytic-sphere", "analytic-RAS", {1: "sphere"}, {"method": name}
                ),
                LabelVolume(
                    truth,
                    "analytic-sphere",
                    "analytic-RAS",
                    {1: "sphere"},
                    {"reference": "analytic center-sampled sphere"},
                ),
            )
            mesh = extract_surface(prediction)
            q = topology(mesh, check_intersections=len(mesh.faces) <= cfg["max_intersection_faces"])
            controlled.append(
                {
                    "case": name,
                    "changed_voxels": int(np.count_nonzero(prediction.array() != truth.array())),
                    "metrics": scored["labels"][0],
                    "topology": q,
                    "resampling": prediction.metadata.get("resampling"),
                    "perturbation": prediction.metadata,
                }
            )
    write_json(output / "segmentation-results.json", results)
    write_json(output / "controlled-boundaries.json", controlled)
    for name, value in results.items():
        pd.DataFrame(
            [{k: v for k, v in row.items() if k != "boundaries"} for row in value["labels"]]
        ).to_csv(output / (name + "-labels.csv"), index=False)
    from soma.benchmarks.plots import segmentation_plots

    segmentation_plots(output, results, images, controlled)
    return report.finish(
        {
            "status": "complete_reference_benchmark"
            if len(results) == 2
            else "partial_missing_reference",
            "datasets": {
                k: {
                    "subject": v["subject"],
                    "macro_Dice": v["macro_Dice"],
                    "labels_scored": len(v["labels"]),
                    "absent_both_labels": v["absent_both_labels"],
                }
                for k, v in results.items()
            },
            "missing": missing,
            "controlled_cases": len(controlled),
            "clinical_or_conductor_certification": False,
            "reference_scope": (
                "BrainWeb simulated tissue truth; Mindboggle manual cortical parcellation only"
            ),
        }
    )


def surface_benchmark(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(output, cfg, source={"reference": "analytic"}, seed=cfg["seed"])
    rows = []
    examples = {}
    with report.stage("sampling_extraction_QC"):
        for name in ["sphere", "ellipsoid", "asymmetric", "shell20", "shell25", "shell30"]:
            for spacing in cfg["voxel_spacing_mm"]:
                scalar = field(name, spacing)
                binary = Volume(
                    (scalar.array() >= 0).astype(np.uint8),
                    scalar.affine_m,
                    "labels",
                    scalar.metadata,
                )
                for method in ["binary", "scalar"]:
                    started = time.perf_counter()
                    mesh = (
                        extract_surface(binary)
                        if method == "binary"
                        else isosurface(scalar, level=0)
                    )
                    extraction_wall = time.perf_counter() - started
                    started = time.perf_counter()
                    row = convergence_record(
                        mesh, name, spacing, method, cfg["max_intersection_faces"]
                    )
                    row["extraction_wall_s"] = extraction_wall
                    row["validation_wall_s"] = time.perf_counter() - started
                    rows.append(row)
                    label = f"{name}:{spacing}:{method}"
                    np.savez_compressed(
                        output / (label.replace(":", "-") + ".npz"),
                        vertices_RAS_m=mesh.vertices.xyz,
                        faces=mesh.faces,
                    )
                    if (
                        name == "sphere"
                        and spacing == min(cfg["voxel_spacing_mm"])
                        and method == "scalar"
                    ):
                        examples = {
                            "xyz_m": mesh.vertices.xyz,
                            "radial_error_mm": (np.linalg.norm(mesh.vertices.xyz, axis=1) - 0.03)
                            * 1000,
                        }
    write_json(output / "convergence.json", rows)
    pd.DataFrame(
        [{k: v for k, v in r.items() if k not in ("topology", "reference")} for r in rows]
    ).to_csv(output / "convergence.csv", index=False)
    from soma.benchmarks.plots import surface_plots

    surface_plots(output, rows, examples)
    return report.finish(
        {
            "status": "complete_analytic_convergence",
            "surfaces": len(rows),
            "reference": "analytic formulas and independent quadrature",
            "rows": [{k: v for k, v in r.items() if k != "topology"} for r in rows],
            "unsupported_full_intersection_cases": sum(
                not r["topology"]["intersection_assessed"] for r in rows
            ),
            "monotonic_convergence_claimed": False,
        }
    )


def repair_audit(config: Path, output: Path) -> dict[str, Any]:
    cfg = configuration(config)
    report = AnatomyReport(
        output, cfg, source={"reference": "analytic sphere tessellation"}, seed=cfg["seed"]
    )
    results = {}
    examples = {}
    with report.stage("repair_and_validation"):
        for name, mesh in repair_cases().items():
            repaired, receipt = repair(
                mesh,
                max_vertex_m=cfg["repair_max_vertex_m"],
                max_area_fraction=cfg["repair_max_area_fraction"],
                max_hole_perimeter_m=cfg["repair_max_hole_perimeter_m"],
                max_hole_area_m2=cfg["repair_max_hole_area_m2"],
            )
            results[name] = receipt
            np.savez_compressed(
                output / (name + ".npz"),
                before_vertices_m=mesh.vertices.xyz,
                before_faces=mesh.faces,
                after_vertices_m=repaired.vertices.xyz,
                after_faces=repaired.faces,
            )
            if name in ("small_hole", "mixed_orientation", "self_intersection"):
                examples[name] = (mesh, repaired)
    write_json(output / "repair-audit.json", results)
    from soma.benchmarks.plots import repair_plots

    repair_plots(output, results, examples)
    return report.finish(
        {
            "status": "complete_computational_repair_audit",
            "cases": results,
            "anatomically_validated": False,
        }
    )
