"""Restricted human MRI figures; these artifacts stay in ignored report trees."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soma.datasets.human_mri import safe_local_output
from soma.validation.plots import save


def overlay_plot(output: Path, arrays: dict[str, Any], dataset: str) -> None:
    safe_local_output(output)
    fig, axes = plt.subplots(1, 4, figsize=(12, 4), layout="constrained")
    for ax, key, title in zip(
        axes,
        ["image_slice", "reference_slice", "prediction_slice", "valid_slice"],
        ["T1", "Manual tissue reference", "Independent multi-Otsu", "Scoring validity"],
        strict=True,
    ):
        cmap = "gray" if key in ("image_slice", "valid_slice") else "tab10"
        ax.imshow(
            arrays[key].T,
            origin="lower",
            cmap=cmap,
            vmin=None if key == "image_slice" else 0,
            vmax=9 if key in ("reference_slice", "prediction_slice") else None,
        )
        ax.set(
            title=title, xlabel="Aligned native voxel index", ylabel="Aligned native voxel index"
        )
    fig.suptitle(
        dataset
        + " | manual reference; shared categorical colors; restricted local research artifact"
    )
    save(output, "native-overlay", fig, arrays)


def cohort_figures(output: Path, rows: list[dict[str, Any]]) -> None:
    safe_local_output(output)
    if not rows:
        return
    dice = np.array(
        [[t["Dice"] if t["Dice"] is not None else -1 for t in r["labels"]] for r in rows]
    )
    assd = np.array(
        [[t["ASSD_mm"] if t["ASSD_mm"] is not None else -1 for t in r["labels"]] for r in rows]
    )
    hd = np.array(
        [[t["HD95_mm"] if t["HD95_mm"] is not None else -1 for t in r["labels"]] for r in rows]
    )
    volume = np.array(
        [
            [
                t["signed_relative_volume_error"]
                if t["signed_relative_volume_error"] is not None
                else -2
                for t in r["labels"]
            ]
            for r in rows
        ]
    )
    indices = np.arange(1, len(rows) + 1)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
    for ax, data, title in zip(
        axes.ravel(),
        [dice, assd, hd, volume],
        ["Dice", "ASSD (mm)", "HD95 (mm)", "Signed relative volume error"],
        strict=True,
    ):
        for i, name in enumerate(["CSF", "GM", "WM"]):
            sentinel = -2 if title == "Signed relative volume error" else -1
            ax.plot(indices, np.ma.masked_equal(data[:, i], sentinel), "o-", label=name)
        ax.set(xlabel="Local case ordinal (subject, not slice)", ylabel=title)
        ax.legend(fontsize=8)
    fig.suptitle(
        rows[0]["dataset"] + " | manual human tissue references vs fixed independent baseline"
    )
    save(
        output,
        "subject-tissue-metrics",
        fig,
        {
            "case_ordinal": indices,
            "Dice": dice,
            "ASSD_mm": assd,
            "HD95_mm": hd,
            "signed_relative_volume_error": volume,
            "undefined_nonnegative_metric_sentinel": -1,
            "undefined_relative_volume_sentinel": -2,
        },
    )
