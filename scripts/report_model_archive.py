"""Plot reviewed aggregate source validation and reload facts, never private weights."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from soma.results.io import inspect_result, read_json

p = argparse.ArgumentParser()
p.add_argument("--summary", required=True, type=Path)
p.add_argument("--evidence", required=True, type=Path)
p.add_argument("--output", required=True, type=Path)
p.add_argument("--preview", required=True, type=Path)
a = p.parse_args()
e = inspect_result(a.summary)["envelope"]
if e["method"] != {"id": "soma.model-release-summary", "version": "1"} or e["payload"]["arrays"]:
    raise ValueError("Reviewed metadata summary required")
d = e["payload"]["values"]
r = read_json(a.evidence)
if (
    d["human_external_accuracy"] is not None
    or r["weights_exported"]
    or r["participant_rows_exported"]
):
    raise ValueError("No human external or restricted artifact export supported")
a.output.mkdir(parents=True, exist_ok=True)
a.preview.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "soma-model-archive-v24"})
labels = ["Majority", "Band-power LR", "CSP LDA", "Riemannian MDM", "Tangent LR"]
methods = d["source_validation"]["methods"]
means = np.array([m["balanced_accuracy"]["mean"] for m in methods]) * 100
lo = np.array([m["balanced_accuracy"]["lower"] for m in methods]) * 100
hi = np.array([m["balanced_accuracy"]["upper"] for m in methods]) * 100


def save(fig, name):
    path = a.output / (name + ".svg")
    fig.savefig(path, bbox_inches="tight", metadata={"Date": None})
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    fig.savefig(a.preview / (name + ".png"), bbox_inches="tight", dpi=150)
    plt.close(fig)


fig, ax = plt.subplots(figsize=(9, 5))
y = np.arange(len(labels))
ax.errorbar(means, y, xerr=[means - lo, hi - means], fmt="o", capsize=4, color="#2166ac")
ax.axvline(50, color="gray", linestyle="--")
ax.set(yticks=y, yticklabels=labels, xlabel="Mean participant balanced accuracy (%)", xlim=(45, 70))
ax.invert_yaxis()
ax.set_title(
    "Reused EEGBCI source cohort: 35 participants, 3 subject folds\n"
    "Fixed historical settings; conditional 95% participant intervals"
)
fig.text(
    0.5,
    0.01,
    "Not untouched validation or external replication; no human external outcomes",
    ha="center",
)
fig.tight_layout(rect=(0, 0.04, 1, 1))
save(fig, "source-validation")
fig, ax = plt.subplots(figsize=(9, 4.7))
values = np.ones((5, 3))
values[3, 2] = np.nan
ax.imshow(values, vmin=0, vmax=1, cmap="Greens", aspect="auto")
for i in range(5):
    for j in range(3):
        ax.text(
            j,
            i,
            "N/A" if i == 3 and j == 2 else "EXACT",
            ha="center",
            va="center",
            color="black" if i == 3 and j == 2 else "white",
        )
ax.set(
    xticks=[0, 1, 2],
    xticklabels=["Labels", "Decision scores", "Supported probabilities"],
    yticks=np.arange(5),
    yticklabels=labels,
)
ax.set_title(
    "1,441 training-session predictions per model\n"
    "Two restarted noneditable processes; fitting disabled"
)
fig.text(
    0.5,
    0.01,
    "Exact dependency snapshot; ordinarily resolved environment remains unsupported",
    ha="center",
)
fig.tight_layout(rect=(0, 0.04, 1, 1))
save(fig, "reload-verification")
print(
    json.dumps(
        {"figures": 2, "scope": "source validation and numeric parity; no external accuracy"}
    )
)
