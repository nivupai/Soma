"""Aggregate-safe research figures; participant forests are kept in private output only."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from soma.eeg_benchmark.protocol import MODELS

LABELS = {
    "dummy": "Majority reference",
    "multiband_lr": "Log band power + LR",
    "csp_lda": "CSP + LDA",
    "riemann_mdm": "Riemannian MDM",
    "tangent_lr": "Tangent space + LR",
}


def figures(aggregate: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"svg.fonttype": "none", "font.size": 10})

    def save(fig: Any, name: str) -> None:
        fig.savefig(output / (name + ".svg"), bbox_inches="tight", metadata={"Date": None})
        fig.savefig(output / (name + ".png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    primary = aggregate["variants"][0]
    fig, ax = plt.subplots(figsize=(10, 5))
    for index, mode in enumerate(("within-subject", "cross-subject")):
        rows = [r for r in primary["methods"] if r["mode"] == mode]
        x = np.arange(len(MODELS)) + (index - 0.5) * 0.25
        means = np.array(
            [r["balanced_accuracy"]["mean"] if r["balanced_accuracy"] else np.nan for r in rows]
        )
        errors = np.array(
            [
                [
                    means[i] - r["balanced_accuracy"]["lower"],
                    r["balanced_accuracy"]["upper"] - means[i],
                ]
                if r["balanced_accuracy"]
                else [np.nan, np.nan]
                for i, r in enumerate(rows)
            ]
        ).T
        ax.errorbar(x, means, yerr=errors, fmt="o", capsize=4, label=mode)
    ax.axhline(0.5, color="gray", linestyle="--", label="balanced chance reference")
    ax.set(
        ylim=(0, 1),
        ylabel="Equal-subject/run balanced accuracy",
        xticks=np.arange(len(MODELS)),
        xticklabels=[LABELS[m] for m in MODELS],
        title=(
            "Historically reused EEGBCI: held-out fitting\n"
            "95% subject bootstrap conditional on fitted source models"
        ),
    )
    ax.tick_params(axis="x", labelrotation=18)
    ax.legend(loc="lower left")
    fig.tight_layout()
    save(fig, "model-comparison")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, mode in zip(axes, ("within-subject", "cross-subject"), strict=True):
        for row in primary["methods"]:
            if row["mode"] != mode:
                continue
            edges = np.asarray(row["distribution_bin_edges"])
            centers = (edges[1:] + edges[:-1]) / 2
            ax.step(centers, row["subject_distribution"], where="mid", label=LABELS[row["model"]])
        ax.set(xlim=(0, 1), xlabel="Subject mean balanced accuracy", title=mode)
    axes[0].set_ylabel("Number of evaluation subjects")
    axes[1].legend(fontsize=8)
    fig.suptitle("Subject-level distributions; no participant identifiers")
    fig.tight_layout()
    save(fig, "subject-distributions")
    fig, axes = plt.subplots(1, 5, figsize=(14, 3.5))
    for ax, model in zip(axes, MODELS, strict=True):
        row = next(
            r for r in primary["methods"] if r["mode"] == "cross-subject" and r["model"] == model
        )
        mat = np.asarray(row["confusion"])
        ax.imshow(mat, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(mat[i, j]), ha="center", va="center")
        ax.set(
            title=LABELS[model],
            xticks=[0, 1],
            yticks=[0, 1],
            xticklabels=["Left", "Right"],
            yticklabels=["Left", "Right"],
            xlabel="Predicted",
        )
    axes[0].set_ylabel("True class")
    fig.suptitle("Zero-shot pooled confusion counts (correlated trials; not independent subjects)")
    fig.tight_layout()
    save(fig, "confusion")
    fig, ax = plt.subplots(figsize=(11, 5))
    for model in MODELS[1:]:
        values = []
        for v in aggregate["variants"]:
            row = next(
                r for r in v["methods"] if r["mode"] == "cross-subject" and r["model"] == model
            )
            values.append(row["balanced_accuracy"]["mean"] if row["balanced_accuracy"] else np.nan)
        ax.plot(np.arange(len(values)), values, "o-", label=LABELS[model])
    ax.axhline(0.5, color="gray", linestyle="--")
    ax.set(
        ylim=(0, 1),
        ylabel="Mean target-subject balanced accuracy",
        xticks=np.arange(len(aggregate["variants"])),
        xticklabels=[v["variant"] for v in aggregate["variants"]],
        title="Prespecified sensitivities; differing QC eligibility and estimands are reported",
    )
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, "sensitivity")
    fig, ax = plt.subplots(figsize=(7, 4))
    for model in ("multiband_lr", "tangent_lr"):
        rows = [r for r in primary.get("adaptation", []) if r["model"] == model]
        if rows:
            ax.plot(
                [r["labeled_target_trials"] for r in rows],
                [
                    r["balanced_accuracy"]["mean"] if r["balanced_accuracy"] else np.nan
                    for r in rows
                ],
                "o-",
                label=LABELS[model],
            )
    ax.axhline(0.5, color="gray", linestyle="--")
    ax.set(
        ylim=(0, 1),
        xlabel="Labeled target run-4 calibration trials",
        ylabel="Mean subject balanced accuracy, test runs8/12",
        title="Target-supervised adaptation is separate from zero-shot transfer",
    )
    ax.legend()
    fig.tight_layout()
    save(fig, "adaptation")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    resource_x = np.arange(len(aggregate["variants"]))
    axes[0].bar(resource_x, [v["wall_seconds"] for v in aggregate["variants"]])
    axes[0].set_ylabel("Wall seconds")
    axes[1].plot(resource_x, [v["process_peak_rss_mib"] for v in aggregate["variants"]], "o-")
    axes[1].set_ylabel("Process cumulative high-water RSS (MiB)")
    for ax in axes:
        ax.set_xticks(
            resource_x, [v["variant"] for v in aggregate["variants"]], rotation=45, ha="right"
        )
    fig.suptitle("Measured resource cost; primary additionally includes adaptation and null refits")
    fig.tight_layout()
    save(fig, "resources")
