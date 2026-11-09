"""Supported BIDS mask exports; statistical maps remain explicit custom reports."""

from importlib.metadata import version
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np

from soma.core.provenance import write_json
from soma.fmri.glm import Estimate
from soma.imaging.nifti import save_nifti
from soma.pipeline.derivatives import official_validate, private_output


def export_estimate(estimate: Estimate, output: Path) -> dict[str, Any]:
    private_output(output)
    derivatives = output / "derivatives/soma"
    derivatives.mkdir(parents=True, exist_ok=False)
    custom = output / "soma-reports"
    custom.mkdir(exist_ok=False)
    run = estimate.run
    source_root = Path(run.provenance.get("source_root", ".")).resolve()
    source = run.provenance["source"]
    description = {
        "Name": "Soma functional analysis masks",
        "BIDSVersion": "1.11.2",
        "DatasetType": "derivative",
        "GeneratedBy": [{"Name": "Soma", "Version": version("soma-neuro")}],
        "SourceDatasets": [{"URL": source_root.as_uri()}],
        "DatasetLinks": {"source": source_root.as_uri()},
    }
    write_json(derivatives / "dataset_description.json", description)
    entity = "sub-" + run.subject
    folder = derivatives / entity
    if run.session != "none":
        entity += "_ses-" + run.session
        folder /= "ses-" + run.session
    entity += "_task-" + run.task + "_run-" + run.run
    if not all(c.isalnum() or c in "_-" for c in entity):
        raise ValueError("Invalid BIDS identity labels")
    folder /= "func"
    folder.mkdir(parents=True)
    maskpath = folder / (entity + "_desc-analysis_mask.nii.gz")
    save_nifti(run.mask, maskpath)
    path = Path(source)
    sources = (
        ["bids:source:" + path.resolve().relative_to(source_root).as_posix()]
        if path.is_file() and path.resolve().is_relative_to(source_root)
        else []
    )
    write_json(
        maskpath.with_name(maskpath.name.removesuffix(".nii.gz") + ".json"),
        {
            "Type": "ROI",
            "SpatialReference": "orig",
            "Sources": sources,
            "Description": "Functional analysis foreground; brain extraction unvalidated",
            "Soma": {
                "SpaceIdentity": run.space,
                "Preprocessing": run.preprocessing,
                "Provenance": run.provenance,
            },
        },
    )
    for name, image in estimate.maps.items():
        values = np.asarray(image.dataobj)
        if not np.isfinite(values).all():
            raise ValueError("Cannot publish nonfinite statistical image")
        target = custom / (entity + "_" + estimate.contrast.name + "_" + name + ".nii.gz")
        nib.save(image, target)
    write_json(
        custom / "contrast.json",
        {
            **estimate.metadata,
            "identity": run.identity,
            "space": run.space,
            "source": run.provenance,
            "standardized_statistical_suffix_claimed": False,
        },
    )
    result = official_validate(derivatives)
    write_json(output / "derivative-validation.json", result)
    return {
        "standardized_derivative": "functional analysis mask only",
        "schema_status": result["status"],
        "statistical_maps": "Soma-specific reports, not standardized BIDS statistics",
    }
