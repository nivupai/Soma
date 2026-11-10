"""Code-owned small synthetic stages, wrapping established Soma scientific methods."""

from typing import Any

import mne
import nibabel as nib
import numpy as np
import pandas as pd
from nilearn.glm.regression import OLSModel, RegressionResults

from soma.core.signal import Signal
from soma.eeg.preprocessing import rereference
from soma.fmri.design import ModelConfig, build_design
from soma.fmri.glm import fit
from soma.fmri.records import FunctionalRun
from soma.imaging.mesh_quality import mesh_quality
from soma.imaging.surfaces import extract_surface
from soma.imaging.validation import validate_volume
from soma.imaging.volumes import Volume
from soma.pipeline.stages import intensity_qc, preprocess
from soma.sdk.synthetic import simulate_fmri, synthetic_signal
from soma.signal.spectral import Spectrum, WelchConfig, welch
from soma.source.inverse import Tikhonov
from soma.source.resolution import Resolution
from soma.workflow.model import WorkflowError
from soma.workflow.runtime import Operation, Registry


def eeg_generate(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if p != {"fs_hz": 160.0, "duration_s": 4.0}:
        raise WorkflowError("Synthetic EEG generator uses bounded 160 Hz, 4 seconds")
    a = synthetic_signal("noisy", fs=160, duration=4, seed=int(seed or 0))
    b = synthetic_signal("sine20", fs=160, duration=4, seed=int(seed or 0))
    return {"recording": {"data": np.stack([a.values, b.values]), "fs_hz": 160.0}}


def eeg_validate(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    data = inputs["recording"]
    raw = mne.io.RawArray(
        data["data"], mne.create_info(["C3", "C4"], data["fs_hz"], "eeg"), verbose=False
    )
    for i, channel in enumerate(raw.ch_names):
        Signal(raw.get_data()[i], data["fs_hz"], channel)
    return {"validated": data}


def eeg_reference(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    data = inputs["validated"]
    return {
        "referenced": {
            "data": rereference(data["data"], p["reference"]),
            "fs_hz": data["fs_hz"],
            "reference": p["reference"],
        }
    }


def eeg_psd(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    data = inputs["referenced"]
    spectra = [welch(Signal(x, data["fs_hz"]), WelchConfig(**p)) for x in data["data"]]
    return {
        "psd": {
            "frequencies": spectra[0].frequencies,
            "density": np.stack([s.density for s in spectra]),
            "metadata": spectra[0].metadata,
        }
    }


def eeg_bands(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    psd = inputs["psd"]
    return {
        "bands": {
            name: [
                Spectrum(psd["frequencies"], row, {}).band_power(*bounds) for row in psd["density"]
            ]
            for name, bounds in p.items()
        }
    }


def mri_generate(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if p:
        raise WorkflowError("Fixed bounded MRI generator takes no shape parameters")
    xyz = np.indices((16, 16, 16)).transpose(1, 2, 3, 0)
    radius = np.linalg.norm(xyz - 7.5, axis=-1)
    signal = np.maximum(6 - radius, 0) * (1 + 0.15 * xyz[..., 0] / 16)
    # Independent noisy intensity; no tissue reference enters segmentation.
    signal += np.random.default_rng(seed).normal(0, 0.01, signal.shape)
    return {"image": Volume(np.maximum(signal, 0.001), np.diag([0.002, 0.002, 0.002, 1.0]))}


def mri_geometry(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    q = validate_volume(inputs["image"])
    if not q["valid"]:
        raise WorkflowError("Synthetic MRI geometry invalid")
    return {"validated": inputs["image"]}


def mri_preprocess(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if p != {
        "n4": {"enabled": True, "iterations": [1], "shrink_factor": 1},
        "resampling": {"enabled": False},
    }:
        raise WorkflowError("Only bounded one-iteration synthetic N4 supported")
    processed, _ = preprocess(inputs["validated"], p)
    return {"processed": processed}


def mri_segment(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    from soma.imaging.segmentation import threshold_mask

    image = inputs["processed"]
    # Existing explicit intensity threshold; heuristic foreground, not tissue/BEM certification.
    labels = threshold_mask(image, threshold=float(p["threshold"]))
    return {"labels": labels}


def mri_qc(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    from soma.imaging.segmentation import region_volumes, validate_mask

    labels, image = inputs["labels"], inputs["processed"]
    validate_mask(labels, image)
    return {
        "qc": {
            "volumes_m3": {str(k): v for k, v in region_volumes(labels).items()},
            "intensity": intensity_qc(image),
            "anatomical_status": "INDETERMINATE",
        }
    }


def mri_surface(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    mesh = extract_surface(inputs["labels"], label=1)
    return {
        "surface": {
            "vertices": mesh.vertices.xyz,
            "faces": mesh.faces,
            "quality": mesh_quality(mesh),
        }
    }


def fmri_generate(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if p != {"n_scans": 40}:
        raise WorkflowError("Bounded synthetic fMRI uses 40 scans")
    run, _ = simulate_fmri(seed=int(seed or 0), n_scans=40)
    return {
        "bold": {
            "image": np.asarray(run.image.dataobj),
            "affine": run.image.affine,
            "mask": run.mask.array(),
            "mask_affine_m": run.mask.affine_m,
            "events": run.events.to_dict("list"),
            "confounds": run.confounds.to_dict("list"),
            "tr": run.tr,
            "metadata": run.provenance,
        }
    }


def functional(value: dict[str, Any]) -> FunctionalRun:
    image = nib.Nifti1Image(value["image"], value["affine"])
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_zooms((*image.header.get_zooms()[:3], value["tr"]))
    return FunctionalRun(
        image=image,
        mask=Volume(value["mask"], value["mask_affine_m"], "labels"),
        events=pd.DataFrame(value["events"]),
        confounds=pd.DataFrame(value["confounds"]),
        tr=value["tr"],
        subject="synthetic",
        session="development",
        task="task",
        run="1",
        provenance=value["metadata"],
        preprocessing="synthetic",
        space="synthetic-RAS",
    )


def fmri_validate(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    run = functional(inputs["bold"])
    if not np.isfinite(np.asarray(run.image.dataobj)).all() or run.n_scans != 40:
        raise WorkflowError("Invalid bounded BOLD data")
    return {"validated": inputs["bold"]}


def model_config() -> ModelConfig:
    return ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))


def fmri_design(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    design, q = build_design(functional(inputs["validated"]), model_config())
    return {
        "design": {
            "values": design.to_numpy(),
            "names": list(design.columns),
            "index": design.index.to_numpy(),
            "diagnostics": q,
        }
    }


def fmri_fit(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    run = functional(inputs["validated"])
    fitted = fit(run, model_config())
    expected = inputs["design"]
    if list(fitted.design.columns) != expected["names"] or not np.array_equal(
        fitted.design.to_numpy(), expected["values"]
    ):
        raise WorkflowError("Fitted design differs from upstream design artifact")
    if len(fitted.model.results_[0]) != 1:
        raise WorkflowError("Only single-group OLS sufficient statistics supported")
    result = next(iter(fitted.model.results_[0].values()))
    return {
        "fit": {
            "theta": result.theta,
            "cov": result.cov,
            "dispersion": result.dispersion,
            "dof": result.df_residuals,
            "design": expected["values"],
            "names": expected["names"],
            "diagnostics": fitted.diagnostics,
            "confirmatory_claim_allowed": False,
        }
    }


def fmri_contrast(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    from soma.fmri.design import Contrast

    stored = inputs["fit"]
    if p.get("confirmatory_claim_allowed") is not False:
        raise WorkflowError("No confirmatory workflow inference permitted")
    design = pd.DataFrame(stored["design"], columns=stored["names"])
    weights = Contrast("workflow-effect", p["weights"]).vector(design)
    # Rehydrate only numeric OLS sufficient statistics using Nilearn's existing contrast method.
    # No pickle, model fitting, input simulation or data-dependent re-estimation here.
    result = RegressionResults(
        stored["theta"],
        np.empty((len(stored["design"]), 0)),
        OLSModel(stored["design"]),
        None,
        None,
        cov=stored["cov"],
        dispersion=stored["dispersion"],
    )
    if result.df_residuals != stored["dof"]:
        raise WorkflowError("Cached OLS residual degrees of freedom differ")
    estimate = result.Tcontrast(weights)
    return {
        "contrast": {
            "effect": np.asarray(estimate.effect),
            "variance": np.asarray(estimate.sd) ** 2,
            "dof": float(estimate.df_den),
            "weights": p["weights"],
            "confirmatory_claim_allowed": False,
        }
    }


def fmri_roi(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    data = inputs["contrast"]
    if data["confirmatory_claim_allowed"] is not False:
        raise WorkflowError("Descriptive summaries only")
    return {
        "roi": {
            "definition": "all explicitly modeled synthetic voxels",
            "mean_effect": float(np.mean(data["effect"])),
            "mean_variance": float(np.mean(data["variance"])),
            "confirmatory_claim_allowed": False,
        }
    }


def source_geometry(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if p:
        raise WorkflowError("Fixed three-source toy geometry")
    return {"geometry": {"positions_m": np.eye(3) * 0.01, "identity": "toy-three-points"}}


def source_forward(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    if not 0.5 <= p["scale"] <= 2:
        raise WorkflowError("Bounded toy forward scale required")
    return {"forward": np.eye(3) * p["scale"]}


def source_inverse(inputs: dict[str, Any], p: dict[str, Any], seed: int | None) -> dict[str, Any]:
    model = Tikhonov(inputs["forward"], p["lambda2"])
    return {"inverse": model.kernel}


def source_reconstruct(
    inputs: dict[str, Any], p: dict[str, Any], seed: int | None
) -> dict[str, Any]:
    forward, kernel = inputs["forward"], inputs["inverse"]
    truth = np.array([1.0, 0.0, 0.0])
    resolution = Resolution(kernel, forward)
    return {
        "source": {
            "estimate": kernel @ (forward @ truth),
            "resolution_diagonal": resolution.diagonal,
            "units": "dimensionless toy",
            "anatomical_status": "NOT_ASSESSED",
        }
    }


def builtins() -> Registry:
    specs = [
        ("eeg.generate", {}, {"recording": "eeg.recording"}, eeg_generate, True),
        (
            "eeg.validate",
            {"recording": "eeg.recording"},
            {"validated": "eeg.validated"},
            eeg_validate,
            False,
        ),
        (
            "eeg.reference",
            {"validated": "eeg.validated"},
            {"referenced": "eeg.referenced"},
            eeg_reference,
            False,
        ),
        ("eeg.psd", {"referenced": "eeg.referenced"}, {"psd": "eeg.psd"}, eeg_psd, False),
        ("eeg.bands", {"psd": "eeg.psd"}, {"bands": "eeg.bands"}, eeg_bands, False),
        ("mri.generate", {}, {"image": "mri.intensity"}, mri_generate, True),
        (
            "mri.geometry",
            {"image": "mri.intensity"},
            {"validated": "mri.validated"},
            mri_geometry,
            False,
        ),
        (
            "mri.preprocess",
            {"validated": "mri.validated"},
            {"processed": "mri.processed"},
            mri_preprocess,
            False,
        ),
        (
            "mri.segment",
            {"processed": "mri.processed"},
            {"labels": "mri.labels"},
            mri_segment,
            False,
        ),
        (
            "mri.qc",
            {"labels": "mri.labels", "processed": "mri.processed"},
            {"qc": "mri.qc"},
            mri_qc,
            False,
        ),
        ("mri.surface", {"labels": "mri.labels"}, {"surface": "mri.surface"}, mri_surface, False),
        ("fmri.generate", {}, {"bold": "fmri.bold"}, fmri_generate, True),
        (
            "fmri.validate",
            {"bold": "fmri.bold"},
            {"validated": "fmri.validated"},
            fmri_validate,
            False,
        ),
        (
            "fmri.design",
            {"validated": "fmri.validated"},
            {"design": "fmri.design"},
            fmri_design,
            False,
        ),
        (
            "fmri.fit",
            {"validated": "fmri.validated", "design": "fmri.design"},
            {"fit": "fmri.fit"},
            fmri_fit,
            False,
        ),
        ("fmri.contrast", {"fit": "fmri.fit"}, {"contrast": "fmri.contrast"}, fmri_contrast, False),
        ("fmri.roi", {"contrast": "fmri.contrast"}, {"roi": "fmri.roi"}, fmri_roi, False),
        ("source.geometry", {}, {"geometry": "source.geometry"}, source_geometry, False),
        (
            "source.forward",
            {"geometry": "source.geometry"},
            {"forward": "source.forward"},
            source_forward,
            False,
        ),
        (
            "source.inverse",
            {"forward": "source.forward"},
            {"inverse": "source.inverse"},
            source_inverse,
            False,
        ),
        (
            "source.reconstruct",
            {"forward": "source.forward", "inverse": "source.inverse"},
            {"source": "source.result"},
            source_reconstruct,
            False,
        ),
    ]
    return Registry(
        [
            Operation(name, ins, outs, fn, stochastic=stochastic)
            for name, ins, outs, fn, stochastic in specs
        ]
    )
