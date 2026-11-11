"""Publish metadata-only blocked audit figures; never export human predictions/weights."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from soma.eeg_benchmark.plots import LABELS
from soma.external_eeg.runtime import read_receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--synthetic", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preview", type=Path, required=True)
    a = p.parse_args()
    d = read_receipt(a.audit)
    r = json.loads(a.synthetic.read_text())["invariants"]
    if (
        d["status"] != "BLOCKED"
        or d["performance"]
        or not r["synthetic_only"]
        or r["actual_human_data_accessed"]
    ):
        raise ValueError(
            "This publisher accepts only blocked human metadata and fictional reference outcomes"
        )
    a.output.mkdir(parents=True, exist_ok=True)
    a.preview.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"svg.fonttype": "none", "font.size": 10})

    def save(fig, name):
        svg = a.output / (name + ".svg")
        fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
        svg.write_text("\n".join(s.rstrip() for s in svg.read_text().splitlines()) + "\n")
        fig.savefig(a.preview / (name + ".png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, values, title in zip(
        axes,
        [[64, 22], [160, 250]],
        ["EEG reference pool: documented channels", "Native sampling rate (Hz)"],
        strict=True,
    ):
        ax.bar(["EEGBCI", "BNCI2014-001"], values, color=["#2166ac", "#d6604d"])
        ax.set_title(title)
        ax.set_ylim(0, max(values) * 1.25)
        for i, v in enumerate(values):
            ax.text(i, v, str(v), ha="center", va="bottom")
    fig.suptitle(
        "Metadata shift only — 0 external human subjects evaluated\n"
        "Original M22 fitted state missing; exact transfer BLOCKED"
    )
    fig.tight_layout()
    save(fig, "transfer-feasibility")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, split in zip(axes, ["subject", "session"], strict=True):
        rows = r["outcomes"][split]
        x = np.arange(len(rows))
        ax.bar(x, [v["mean"] for v in rows], color="#2166ac")
        ax.axhline(0.5, color="gray", linestyle="--")
        ax.set(
            ylim=(0, 1),
            xticks=x,
            xticklabels=[LABELS[v["model"]] for v in rows],
            title=f"Fictional {split} split; target N={rows[0]['subjects']}",
            ylabel="Toy balanced accuracy",
        )
        ax.tick_params(axis="x", rotation=25)
    fig.suptitle(
        "SYNTHETIC NUMERICAL REFERENCES ONLY\n"
        "No human accuracy, confidence, or external replication claim"
    )
    fig.tight_layout()
    save(fig, "synthetic-reference")
    (a.output / "synthetic-reference.json").write_text(json.dumps(r, indent=2) + "\n")


if __name__ == "__main__":
    main()
