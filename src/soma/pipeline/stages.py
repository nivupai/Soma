"""Conservative image stages reusing Volume, SimpleITK bridge and surface QC."""

import time
from pathlib import Path
from typing import Any

import numpy as np
import SimpleITK as sitk

from soma.benchmarks.topology import topology
from soma.geometry import Frame, Transform
from soma.imaging.nifti import load_nifti
from soma.imaging.registration import from_sitk, to_sitk
from soma.imaging.resampling import resample
from soma.imaging.segmentation import region_volumes, require_labels, threshold_mask, validate_mask
from soma.imaging.surfaces import extract_surface
from soma.imaging.validation import validate_volume
from soma.imaging.volumes import Volume
from soma.pipeline.backends import BACKENDS
from soma.pipeline.contracts import StageSpec, transform_receipt


def graph(config: dict[str, Any]) -> list[StageSpec]:
    return [
        StageSpec(
            "ingestion",
            (),
            {"record": "record"},
            {"native": "Volume"},
            {"affine_policy": config["affine_policy"]},
        ),
        StageSpec("geometry", ("ingestion",), {"native": "Volume"}, {"geometry": "dict"}),
        StageSpec(
            "intensity",
            ("geometry",),
            {"native": "Volume", "geometry": "dict"},
            {"intensity_qc": "dict"},
        ),
        StageSpec(
            "preprocessing",
            ("intensity",),
            {"native": "Volume", "intensity_qc": "dict"},
            {"processed": "Volume", "preprocess_qc": "dict"},
            {"n4": config["n4"], "resampling": config["resampling"]},
            software=("SimpleITK", "nibabel"),
        ),
        StageSpec(
            "mask",
            ("preprocessing",),
            {"processed": "Volume", "record": "record"},
            {"mask": "optionalVolume", "mask_qc": "dict"},
            config["mask"],
        ),
        StageSpec(
            "segmentation",
            ("mask",),
            {"processed": "Volume", "mask": "optionalVolume", "record": "record"},
            {"labels": "Volume", "backend_qc": "dict"},
            {**config["backend"], "apply_mask": config["mask"]["apply_to_segmentation"]},
        ),
        StageSpec(
            "label_validation",
            ("segmentation",),
            {"labels": "Volume", "processed": "Volume"},
            {"label_qc": "dict"},
        ),
        StageSpec(
            "surface",
            ("label_validation",),
            {"labels": "Volume", "label_qc": "dict"},
            {"surfaces": "list"},
            config["surfaces"],
        ),
        StageSpec(
            "mesh_qc", ("surface",), {"surfaces": "list"}, {"mesh_qc": "dict"}, config["surfaces"]
        ),
        StageSpec(
            "report",
            ("mesh_qc",),
            {
                "geometry": "dict",
                "intensity_qc": "dict",
                "preprocess_qc": "dict",
                "mask_qc": "dict",
                "label_qc": "dict",
                "mesh_qc": "dict",
            },
            {"qc": "dict"},
        ),
        StageSpec(
            "export",
            ("report",),
            {"processed": "Volume", "labels": "Volume", "mask": "optionalVolume", "qc": "dict"},
            {"export_ready": "dict"},
        ),
    ]


def intensity_qc(image: Volume) -> dict[str, Any]:
    x = image.array()
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite MRI intensities")
    if np.ptp(x) <= 0:
        raise ValueError("Constant MRI has no usable intensity contrast")
    positive = x[x > 0]
    if not len(positive):
        raise ValueError("No positive T1 intensities")
    return {
        "status": "PASS",
        "numerical": "finite, nonconstant",
        "range": [float(x.min()), float(x.max())],
        "foreground_definition": "positive voxels, statistics only; no normalization",
        "foreground_quantiles": np.quantile(positive, [0.01, 0.25, 0.5, 0.75, 0.99]).tolist(),
        "mean": float(positive.mean()),
        "SD": float(positive.std()),
        "intensity_scale": "native arbitrary MRI units",
        "histogram": np.histogram(positive, bins=64)[0].tolist(),
        "histogram_edges": np.histogram(positive, bins=64)[1].tolist(),
    }


def preprocess(image: Volume, parameters: dict[str, Any]) -> tuple[Volume, dict[str, Any]]:
    result = image
    diagnostics: dict[str, Any] = {
        "n4": {"enabled": False},
        "transforms": [],
        "input_geometry": image.geometry(),
    }
    n4 = parameters["n4"]
    if n4["enabled"]:
        iterations = n4["iterations"]
        shrink = n4["shrink_factor"]
        if (
            not iterations
            or len(iterations) > 4
            or any(not isinstance(n, int) or not 1 <= n <= 100 for n in iterations)
            or not isinstance(shrink, int)
            or not 1 <= shrink <= 4
        ):
            raise ValueError("Bounded N4 iterations/shrink factor required")
        sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(1)
        native = sitk.Cast(to_sitk(image), sitk.sitkFloat32)
        mask = sitk.Cast(native > 0, sitk.sitkUInt8)
        if np.count_nonzero(image.array() > 0) < 16:
            raise ValueError("Insufficient positive support for N4")
        small = sitk.Shrink(native, [shrink] * 3)
        small_mask = sitk.Shrink(mask, [shrink] * 3)
        correction = sitk.N4BiasFieldCorrectionImageFilter()
        correction.SetMaximumNumberOfIterations(iterations)
        started = time.perf_counter()
        correction.Execute(small, small_mask)
        logfield = correction.GetLogBiasFieldAsImage(native)
        corrected = native / sitk.Exp(logfield)
        candidate = from_sitk(corrected)
        if not image.same_grid(candidate):
            raise ValueError("N4 changed physical image geometry")
        result = Volume(candidate.data, candidate.affine_m, "intensity", image.metadata)
        diagnostics["n4"] = {
            "enabled": True,
            "iterations": iterations,
            "shrink_factor": shrink,
            "elapsed_iterations": int(correction.GetElapsedIterations()),
            "current_level": int(correction.GetCurrentLevel()),
            "convergence_measure": float(correction.GetCurrentConvergenceMeasurement()),
            "convergence_threshold": float(correction.GetConvergenceThreshold()),
            "wall_s": time.perf_counter() - started,
            "mask_source": "positive input support, not a validated brain mask",
            "units": "native intensity scale; no z-scoring",
        }
    spatial = parameters["resampling"]
    if spatial["enabled"]:
        reference = load_nifti(Path(spatial["reference"]))
        mapping = Transform(Frame.RAS, Frame.RAS, np.eye(4))
        before = result
        result = resample(result, reference, reference_to_source=mapping, order=1)
        diagnostics["transforms"].append(
            transform_receipt(
                mapping,
                before.geometry(),
                reference.geometry(),
                interpolation="linear",
                provenance="explicit voxel-grid resampling; no registration",
            )
        )
    if not np.isfinite(result.array()).all():
        raise ValueError("Preprocessing produced nonfinite data")
    diagnostics["output_geometry"] = result.geometry()
    return result, diagnostics


def execute_stage(
    name: str, inputs: dict[str, Any], parameters: dict[str, Any], loader: Any
) -> dict[str, Any]:
    if name == "ingestion":
        return {"native": loader()}
    if name == "geometry":
        q = validate_volume(inputs["native"])
        if not q["valid"] or q["voxel_roundtrip_max_voxels"] > 1e-7:
            raise ValueError("MRI geometry roundtrip failed")
        return {"geometry": q}
    if name == "intensity":
        return {"intensity_qc": intensity_qc(inputs["native"])}
    if name == "preprocessing":
        image, q = preprocess(inputs["native"], parameters)
        return {"processed": image, "preprocess_qc": q}
    if name == "mask":
        image = inputs["processed"]
        policy = parameters["policy"]
        mask = None
        if policy == "threshold":
            mask = threshold_mask(image)
        elif policy == "import":
            if parameters.get("subject") != inputs["record"]["subject"]:
                raise ValueError("Mask subject identity differs")
            if parameters.get("input_sha256") != image.metadata.get("source_sha256"):
                raise ValueError("Imported mask input MRI identity differs")
            mask = load_nifti(Path(parameters["path"]), kind="labels")
            validate_mask(mask, image)
        elif policy != "none":
            raise ValueError("Mask policy must be none, threshold or import")
        if mask is not None:
            validate_mask(mask, image)
            coverage = float(np.mean(mask.array() != 0))
            if coverage <= 0 or coverage >= 1:
                raise ValueError("Empty or all-volume mask is not a usable brain/foreground mask")
        else:
            coverage = None
        return {
            "mask": mask,
            "mask_qc": {
                "source": policy,
                "coverage": coverage,
                "anatomical_status": "INDETERMINATE",
                "warning": "heuristic foreground/import provenance, not certified brain extraction",
            },
        }
    if name == "segmentation":
        image = inputs["processed"]
        if parameters["apply_mask"]:
            if inputs["mask"] is None:
                raise ValueError("Mask application requested without mask")
            image = Volume(
                np.where(inputs["mask"].array() != 0, image.array(), 0),
                image.affine_m,
                "intensity",
                image.metadata,
            )
        backend = BACKENDS.get(parameters["name"])
        if backend is None:
            raise ValueError("Segmentation backend not registered; no implicit installation")
        labels, q = backend.segment(
            image, subject=inputs["record"]["subject"], parameters=parameters
        )
        required = {
            "backend",
            "version",
            "model",
            "input_contrast",
            "ontology",
            "mapping",
            "native_geometry",
            "runtime_s",
            "warnings",
            "reference_used",
            "subject",
        }
        if (
            not required.issubset(q)
            or q["subject"] != inputs["record"]["subject"]
            or q["reference_used"] is not False
        ):
            raise ValueError("Backend output identity/provenance is incompatible")
        return {"labels": labels, "backend_qc": q}
    if name == "label_validation":
        labels = inputs["labels"]
        data = require_labels(labels)
        if not labels.same_grid(inputs["processed"]) or not set(np.unique(data)).issubset(
            {0, 1, 2, 3}
        ):
            raise ValueError("Segmentation geometry or label ontology incompatible")
        return {
            "label_qc": {
                "status": "PASS",
                "volumes_mm3": {str(k): v * 1e9 for k, v in region_volumes(labels).items()},
                "absent_tissues": [k for k in [1, 2, 3] if not np.any(data == k)],
                "anatomical_plausibility": "INDETERMINATE",
            }
        }
    if name == "surface":
        return {
            "surfaces": [
                extract_surface(inputs["labels"], label=int(k)) for k in parameters["labels"]
            ]
        }
    if name == "mesh_qc":
        rows = [
            topology(m, check_intersections=len(m.faces) <= parameters["intersection_face_limit"])
            for m in inputs["surfaces"]
        ]
        return {
            "mesh_qc": {
                "status": "INDETERMINATE" if not rows else "ASSESSED",
                "surfaces": rows,
                "anatomical_certification": False,
            }
        }
    if name == "report":
        return {
            "qc": {
                **inputs,
                "numerical_status": "PASS",
                "anatomical_status": "INDETERMINATE",
                "clinical_validation": False,
                "BEM_readiness": "INDETERMINATE",
            }
        }
    if name == "export":
        return {
            "export_ready": {
                "geometry": inputs["processed"].geometry(),
                "qc_status": inputs["qc"]["numerical_status"],
            }
        }
    raise ValueError("Unknown processing stage")
