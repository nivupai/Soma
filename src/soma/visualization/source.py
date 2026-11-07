"""Headless scientific source figures; plotted arrays live beside every figure."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soma.source.forward import ForwardModel


def _save(fig: Any, output: Path, name: str, **arrays: Any) -> None:
    fig.savefig(output / f"{name}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    np.savez_compressed(output / f"{name}-figure-data.npz", **arrays)


def _map(ax: Any, xyz: Any, values: Any, title: str, symmetric: bool = False) -> None:
    vmax = float(np.max(np.abs(values))) or 1
    artist = ax.scatter(
        xyz[:, 0] * 1000,
        xyz[:, 1] * 1000,
        c=values,
        s=8,
        cmap="RdBu_r" if symmetric else "viridis",
        vmin=-vmax if symmetric else 0,
        vmax=vmax,
    )
    ax.set(xlabel="Head x (mm)", ylabel="Head y (mm)", title=title)
    ax.set_aspect("equal")
    plt.colorbar(artist, ax=ax, shrink=0.7)


def forward_figures(output: Path, forward: ForwardModel) -> None:
    xyz = forward.coordinates.points.xyz
    sensors = np.array([c["loc"][:3] for c in forward.info["chs"]])
    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(projection="3d")
    import mne

    from soma.geometry import Frame, Points, Transform

    # Source spaces retain their anatomy root; no new resource fetch is needed.
    subjects_dir = Path(forward.anatomy["subjects_dir"])
    scalp_mm, _ = mne.read_surface(subjects_dir / "fsaverage/bem/outer_skin.surf", verbose=False)
    head_to_mri = Transform.from_mne(
        mne.read_trans(subjects_dir / "fsaverage/bem/fsaverage-trans.fif", verbose=False),
        template=True,
    )
    scalp = head_to_mri.inverse().apply(Points.from_mm(scalp_mm, Frame.TEMPLATE_MRI)).xyz
    ax.scatter(*scalp[::5].T * 1000, s=1, alpha=0.08, color="grey", label="template scalp")
    ax.scatter(*xyz.T * 1000, s=2, alpha=0.35, label="fsaverage white sources")
    ax.scatter(*sensors.T * 1000, s=14, color="red", label="template sensors")
    ax.set(
        xlabel="Head x (mm)",
        ylabel="Head y (mm)",
        zlabel="Head z (mm)",
        title="Template electrode / cortical geometry",
    )
    ax.legend()
    _save(
        fig, output, "electrode-head", source_head_m=xyz, sensors_head_m=sensors, scalp_head_m=scalp
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    trans = np.asarray(forward.native_free["mri_head_t"]["trans"])
    axes[0].imshow(trans, cmap="RdBu_r")
    axes[0].set(
        title="Template MRI → head (metres)", xlabel="Homogeneous column", ylabel="Homogeneous row"
    )
    for frame, origin in (("head", np.zeros(3)), ("MRI origin in head", trans[:3, 3])):
        axes[1].scatter(origin[0] * 1000, origin[2] * 1000, label=frame)
    axes[1].set(xlabel="Head x (mm)", ylabel="Head z (mm)", title="Distinct coordinate origins")
    axes[1].legend()
    _save(fig, output, "coordinate-frames", mri_to_head=trans)
    fig, ax = plt.subplots(figsize=(7, 5))
    _map(
        ax, xyz, xyz[:, 2] - np.min(xyz[:, 2]), "fsaverage ico3: superior projection, depth overlap"
    )
    _save(
        fig, output, "cortical-source-space", source_head_m=xyz, source_indices=np.arange(len(xyz))
    )
    fig, ax = plt.subplots(figsize=(10, 4))
    limit = float(np.quantile(np.abs(forward.matrix), 0.99))
    image = ax.imshow(forward.matrix, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit)
    ax.set(
        xlabel="Ordered signed cortical normal source",
        ylabel="EEG channel",
        title="Average-referenced lead field [V/(A m)] (99th percentile color limits)",
    )
    fig.colorbar(image, ax=ax)
    _save(fig, output, "lead-field", lead_field=forward.matrix)
    singular = np.linalg.svd(forward.matrix, compute_uv=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.semilogy(np.arange(1, len(singular) + 1), singular, "o-")
    ax.set(
        xlabel="Singular index",
        ylabel="Singular value [V/(A m)]",
        title="Lead-field spectrum; average-reference null direction",
    )
    _save(fig, output, "singular-spectrum", singular_values=singular)


def simulation_figures(
    output: Path,
    forward: ForwardModel,
    frame: pd.DataFrame,
    tradeoff: pd.DataFrame,
    example: dict[str, Any],
) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    for depth, group in tradeoff.groupby("depth"):
        ax.loglog(group["residual_norm"], group["penalty_norm_Am"], "o-", label=f"depth={depth}")
        primary = group[np.isclose(group["lambda2"], 1 / 9)].iloc[0]
        ax.annotate(
            "λ²=1/9",
            (primary["residual_norm"], primary["penalty_norm_Am"]),
            xytext=(8, 8 if depth else -14),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set(
        xlabel="Sensor residual norm (V)",
        ylabel="Current estimate norm (A m)",
        title="Fixed grid; no truth-selected regularization",
    )
    ax.legend()
    _save(fig, output, "regularization-tradeoff", data=tradeoff.to_numpy())
    xyz = forward.coordinates.points.xyz
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    truth_rms = np.sqrt(np.mean(example["truth"] ** 2, axis=1))
    estimate_rms = np.sqrt(np.mean(example["estimate"] ** 2, axis=1))
    _map(axes[0], xyz, truth_rms, "Synthetic ground truth RMS [A m]")
    active = np.flatnonzero(truth_rms)
    axes[0].scatter(xyz[active, 0] * 1000, xyz[active, 1] * 1000, marker="x", color="red", s=60)

    _map(axes[1], xyz, estimate_rms, "MNE reconstruction RMS [A m]; 10 dB")
    _save(
        fig,
        output,
        "synthetic-recovery",
        source_head_m=xyz,
        truth_rms_Am=truth_rms,
        estimate_rms_Am=estimate_rms,
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    for scenario, group in frame.groupby("scenario"):
        values = group.groupby("snr_db")["mean_assigned_peak_euclidean_m"].agg(["mean", "std"])
        ax.errorbar(
            values.index,
            values["mean"] * 1000,
            yerr=values["std"] * 1000,
            marker="o",
            label=str(scenario),
            capsize=2,
        )
    ax.set(
        xlabel="Controlled sensor SNR (dB)",
        ylabel="Assigned peak Euclidean error (mm)",
        title="Synthetic recovery; mean ± SD across 10 noise realizations",
    )
    ax.legend(fontsize=8)
    _save(
        fig,
        output,
        "localization-versus-snr",
        scenario=frame["scenario"].to_numpy(dtype=str),
        snr_db=frame["snr_db"].to_numpy(dtype=float),
        peak_euclidean_error_m=frame["mean_assigned_peak_euclidean_m"].to_numpy(dtype=float),
    )


def resolution_figure(output: Path, forward: ForwardModel, psf: Any, index: int) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    xyz = forward.coordinates.points.xyz
    _map(ax, xyz, psf, "Template signed point-spread function; λ²=1/9", True)
    ax.scatter(
        xyz[index, 0] * 1000,
        xyz[index, 1] * 1000,
        marker="x",
        s=80,
        color="black",
        label="Injected source",
    )
    ax.legend()
    _save(fig, output, "point-spread", psf=psf, true_index=index, source_head_m=xyz)


def power_figure(output: Path, forward: ForwardModel, maps: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    for ax, (band, code) in zip(
        axes.flat, (("mu", "T1"), ("mu", "T2"), ("beta", "T1"), ("beta", "T2")), strict=True
    ):
        _map(
            ax,
            forward.coordinates.points.xyz,
            maps[f"MNE_{band}_{code}_log_ratio_to_rest"],
            f"{band}: {code}/rest log trial-power ratio",
            True,
        )
    fig.suptitle(
        (
            "Template exploratory source power, subject 1; equal mean of runs 4/8/12\n"
            "Superior projection overlaps depths; no individualized anatomical localization"
        ),
        fontsize=12,
    )
    _save(
        fig,
        output,
        "exploratory-source-power",
        source_head_m=forward.coordinates.points.xyz,
        **maps,
    )
