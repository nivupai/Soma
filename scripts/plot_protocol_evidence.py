"""Render observed drift classifications; missing numeric outcomes are never zero-filled."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = json.loads(args.report.read_text())
    categories = [
        "DATA_DRIFT",
        "PROTOCOL_DRIFT",
        "IMPLEMENTATION_DRIFT",
        "EXECUTION_ENVIRONMENT_DRIFT",
        "NUMERICAL_DRIFT",
        "MEASUREMENT_OR_OUTCOME_DRIFT",
        "MISSING_OR_UNVERIFIABLE_EVIDENCE",
    ]
    labels = []
    rows = []
    for family, item in report["families"].items():
        for case, evidence in item["cases"].items():
            labels.append(f"{family.upper()} / {case}\n{evidence['status']}")
            found = {d["category"] for d in evidence["drift"]}
            rows.append([int(c in found) for c in categories])
    fig, ax = plt.subplots(figsize=(13, 10), layout="constrained")
    ax.imshow(np.array(rows), cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_xticks(range(len(categories)), [c.replace("_", "\n") for c in categories], fontsize=8)
    ax.xaxis.tick_top()
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            ax.text(
                j,
                i,
                "observed" if value else "—",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if value else "#718096",
            )
    fig.suptitle(
        "Observed synthetic replay evidence\n"
        "No biological drift or confirmatory replication established",
        fontsize=13,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()
