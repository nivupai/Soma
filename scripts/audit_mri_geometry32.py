"""Nonidentifying native geometry inventory for the already frozen labeled cohort."""

import argparse
import collections
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from soma.datasets.human_mri import corner_displacement_mm, safe_local_output


def run(local, output):
    safe_local_output(local)
    records = json.loads((local / "inventory.private.json").read_text())["subjects"]
    rows = []
    for dataset in ["ibsr-v2", "mrbrains13"]:
        images = [
            nib.load(r[k])
            for r in records
            if r["dataset"] == dataset
            for k in ["image", "reference"]
        ]
        errors = [
            corner_displacement_mm(im.get_qform(), im.get_sform(), im.shape)
            for im in images
            if int(im.header["qform_code"]) and int(im.header["sform_code"])
        ]
        spacing = np.array([im.header.get_zooms()[:3] for im in images])
        rows.append(
            dict(
                dataset=dataset,
                image_reference_files=len(images),
                coded_sform_files=sum(int(im.header["sform_code"]) > 0 for im in images),
                coded_qform_files=sum(int(im.header["qform_code"]) > 0 for im in images),
                qform_sform_max_corner_difference_mm=max(errors) if errors else None,
                spacing_axis_min_mm=spacing.min(0).astype(float).tolist(),
                spacing_axis_max_mm=spacing.max(0).astype(float).tolist(),
                storage_orientations=dict(
                    collections.Counter("".join(nib.aff2axcodes(im.affine)) for im in images)
                ),
            )
        )
    results = json.loads((local / "tissue-results.private.json").read_text())
    output.write_text(
        json.dumps(
            dict(
                schema="soma.mri-dataset-geometry-aggregate/1",
                data=rows,
                reference_resampling_cases=sum(r["automatic_resampling"] for r in results),
                intensity_alignment_cases=sum(r["resampled_intensity"] for r in results),
                hidden_test_data_opened=False,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("local", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.local, a.output)
