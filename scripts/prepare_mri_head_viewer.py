"""Explicit local operator action; participant assets never enter public packages."""

import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from soma.anatomy.head_models import MRIFrameChain
from soma.datasets.human_mri import align_t1, load_human, mapped_reference, safe_local_output
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points


def write_nifti(data, affine_mm, path):
    image = nib.Nifti1Image(data, affine_mm)
    image.header.set_xyzt_units("mm")
    image.set_qform(affine_mm, 2)
    image.set_sform(affine_mm, 2)
    nib.save(image, path)


def prepare(study, output, config, base=None):
    safe_local_output(output)
    safe_local_output(config)
    output.mkdir(parents=True, exist_ok=False)
    summary = json.loads((study / "public-summary.json").read_text())
    assets = SampleAssets()
    image = nib.load(assets.subject_dir / "mri/T1.mgz")
    aseg = nib.load(assets.subject_dir / "mri/aseg.mgz")
    chain = MRIFrameChain.from_mgh(image, assets.transform)
    affine = chain.voxel_to_surface_m.copy()
    affine[:3] *= 1000
    write_nifti(np.asarray(image.dataobj, dtype=np.float32), affine, output / "anatomy.nii.gz")
    labels = np.asarray(aseg.dataobj)
    tissue = np.zeros(labels.shape, np.uint8)
    tissue[np.isin(labels, [4, 5, 14, 15, 24, 43, 44])] = 1
    tissue[np.isin(labels, [3, 42, 10, 49, 11, 50, 12, 51, 13, 52, 17, 53, 18, 54, 26, 58])] = 2
    tissue[np.isin(labels, [2, 41])] = 3
    write_nifti(tissue, affine, output / "automated-tissues.nii.gz")
    cfg = json.loads(base.read_text()) if base else {"roots": {}, "entries": []}
    cfg["roots"]["m32-local-only"] = str(output.resolve())
    cfg["entries"].append(
        dict(
            id="m32-authorized-mri",
            kind="mri",
            label="MRI-derived head anatomy (local only)",
            root="m32-local-only",
            file="anatomy.nii.gz",
            segmentation="automated-tissues.nii.gz",
            subject="operator-local-anatomy",
            frame="MRI surface RAS (explicit tkregister affine), mm",
            units="MRI intensity",
            synthetic=False,
            provenance=(
                "Authorized local MNE educational anatomy; provided automated FreeSurfer "
                "tissue labels, not independent truth; no redistribution"
            ),
        )
    )
    if summary["anatomy_status"] != "NOT_READY_FOR_FORWARD_MODEL":
        with np.load(study / "geometry-3/geometry.npz", allow_pickle=False) as z:
            meshes = [
                dict(vertices_m=z[f"v{i}"].tolist(), faces=z[f"f{i}"].tolist(), boundary=name)
                for i, name in enumerate(["inner_skull", "outer_skull", "scalp"])
            ]
        info = assets.eeg_info()
        electrodes = assets.transform.apply(
            Points(
                np.array([c["loc"][:3] for c in info["chs"]]),
                Frame.HEAD,
            )
        ).xyz
        packet = dict(
            schema="soma.local-anatomy-view/1",
            status=summary["anatomy_status"],
            frame="MRI_surface_RAS_m",
            meshes=meshes,
            electrodes_m=electrodes.tolist(),
            redistribution_permitted=False,
        )
        (output / "conductor.private.json").write_text(
            json.dumps(packet, separators=(",", ":")) + "\n"
        )
        cfg["entries"].append(
            dict(
                id="m32-authorized-conductor",
                kind="anatomical-model",
                label="MRI-derived FLASH conductor (local only)",
                root="m32-local-only",
                file="conductor.private.json",
                frame="MRI_surface_RAS_m",
                units="m",
                synthetic=False,
                provenance=(
                    "Explicit operator-selected private MRI-derived geometry; "
                    "QC only, no anatomical accuracy"
                ),
            )
        )
    # Independent manual reference and independent prediction shown as separately named views.
    inventory = json.loads((study / "inventory.private.json").read_text())
    r = next(x for x in inventory["subjects"] if x["dataset"] == "ibsr-v2")
    image = load_human(
        Path(r["image"]), dataset=r["dataset"], subject=r["subject"], role="intensity"
    )
    native = load_human(
        Path(r["reference"]), dataset=r["dataset"], subject=r["subject"], role="labels"
    )
    image, _ = align_t1(image, native, dataset=r["dataset"])
    ref, _ = mapped_reference(native, r["dataset"])
    a = image.affine_m.copy()
    a[:3] *= 1000
    write_nifti(image.array().astype(np.float32), a, output / "reference-case-image.nii.gz")
    write_nifti(ref.array().astype(np.uint8), a, output / "manual-tissues.nii.gz")
    p = nib.load(study / "tissue-000/prediction.nii.gz")
    write_nifti(np.asarray(p.dataobj), a, output / "independent-prediction.nii.gz")
    for name, labels, title in [
        ("reference", "manual-tissues.nii.gz", "Manual tissue reference (local only)"),
        (
            "prediction",
            "independent-prediction.nii.gz",
            "Independent intensity prediction (local only)",
        ),
    ]:
        cfg["entries"].append(
            dict(
                id="m32-tissue-" + name,
                kind="mri",
                label=title,
                root="m32-local-only",
                file="reference-case-image.nii.gz",
                segmentation=labels,
                subject="operator-local-tissue-reference",
                frame="native MRI scanner RAS, mm",
                units="MRI intensity",
                synthetic=False,
                provenance=(
                    "Authorized private IBSR methods evaluation; "
                    "no skull/scalp validation or redistribution"
                ),
            )
        )
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(cfg, indent=2) + "\n")
    print("Explicit local anatomy viewer allowlist written; no participant assets packaged")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("study", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--base", type=Path)
    a = p.parse_args()
    prepare(a.study, a.output, a.config, a.base)
