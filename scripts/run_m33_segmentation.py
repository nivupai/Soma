"""M33 segmentation benchmark: control vs masked multi-Otsu vs SynthSeg on 23 labeled cases.

Refuses to score until docs/MILESTONE33_SEGMENTATION_PROTOCOL.md is sealed in
configs/m33-segmentation-freeze.json. Participant outputs stay in ignored local storage.

    python -m scripts.run_m33_segmentation --synthseg-cmd "<cmd {input} {output}>" \
        --phase development --output reports/milestone33/segmentation
"""

import argparse
import json
import shlex
import subprocess
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from soma.benchmarks.segmentation import (
    LabelVolume,
    intensity_baseline,
    masked_intensity_baseline,
    score,
)
from soma.core.provenance import sha256, write_json
from soma.datasets.external_anatomy import TISSUES
from soma.datasets.human_mri import (
    align_t1,
    discover_human,
    load_human,
    mapped_reference,
    safe_local_output,
)
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume
from soma.pipeline.synthseg import intracranial_mask, map_synthseg, to_native_grid
from soma.validation.cohort import subject_interval

PROTOCOL = Path("docs/MILESTONE33_SEGMENTATION_PROTOCOL.md")
FREEZE = Path("configs/m33-segmentation-freeze.json")
METHODS = ("multiotsu_control", "multiotsu_masked", "synthseg")


def require_frozen_protocol() -> dict[str, Any]:
    if not FREEZE.exists():
        raise SystemExit("M33 protocol not frozen: owner approval and seal required before scoring")
    seal = json.loads(FREEZE.read_text())
    if seal.get("protocol_sha256") != sha256(PROTOCOL) or not seal.get("owner_approved"):
        raise SystemExit("M33 protocol seal mismatch or not owner-approved; scoring refused")
    return dict(seal)


def run_synthseg(command: str, image_path: Path, cache: Path) -> Path:
    out = cache / "synthseg.nii.gz"
    if out.exists():
        return out
    cache.mkdir(parents=True, exist_ok=True)
    argv = [a.format(input=image_path, output=out) for a in shlex.split(command)]
    start = time.perf_counter()
    subprocess.run(argv, check=True)
    (cache / "runtime.json").write_text(json.dumps({"runtime_s": time.perf_counter() - start}))
    return out


def predictions(
    image: Volume, synthseg_path: Path, *, subject: str, space: str
) -> dict[str, LabelVolume]:
    raw = load_nifti(synthseg_path, policy="sform", kind="labels")
    mapped, receipt = to_native_grid(map_synthseg(raw), image)
    raw_native, _ = to_native_grid(raw, image)
    mask = intracranial_mask(raw_native)
    common = {"input_sha256": image.metadata["source_sha256"], "truth_used": False}
    volumes: dict[str, tuple[Volume, dict[str, Any]]] = {
        "multiotsu_control": (intensity_baseline(image), {"tool": "frozen multi-Otsu"}),
        "multiotsu_masked": (
            masked_intensity_baseline(image, mask),
            {"tool": "multi-Otsu inside SynthSeg intracranial mask"},
        ),
        "synthseg": (
            mapped,
            {
                "tool": "SynthSeg 2.0",
                "output_sha256": sha256(synthseg_path),
                "native_grid_return": receipt,
            },
        ),
    }
    return {
        name: LabelVolume(
            Volume(vol.array(), vol.affine_m, "labels", {"subject": subject}),
            subject,
            space,
            TISSUES,
            {**common, **extra},
        )
        for name, (vol, extra) in volumes.items()
    }


def evaluate(record: dict[str, Any], command: str, output: Path) -> list[dict[str, Any]]:
    dataset, subject = record["dataset"], record["subject"]
    image = load_human(Path(record["image"]), dataset=dataset, subject=subject, role="intensity")
    native = load_human(Path(record["reference"]), dataset=dataset, subject=subject, role="labels")
    image, _ = align_t1(image, native, dataset=dataset)
    case = output / "cases" / subject.replace(":", "_")
    synth = run_synthseg(command, Path(record["image"]), case)
    reference, valid = mapped_reference(native, dataset)
    reference_lv = LabelVolume(
        reference, subject, record["space"], TISSUES, {"sha256": native.metadata["source_sha256"]}
    )
    rows = []
    for method, prediction in predictions(
        image, synth, subject=subject, space=record["space"]
    ).items():
        metrics = score(
            prediction, reference_lv, valid_mask=valid if dataset == "mrbrains13" else None
        )
        write_json(case / f"{method}-metrics.json", metrics)
        for t in metrics["labels"]:
            rows.append(
                {
                    "dataset": dataset,
                    "subject": subject,
                    "partition": record["partition"],
                    "method": method,
                    **{k: v for k, v in t.items() if k != "boundaries"},
                }
            )
    return rows


def summarize(table: pd.DataFrame, seed: int) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for keys, group in table.groupby(["dataset", "method", "name"]):
        dataset, method, tissue = (str(k) for k in keys)
        entry = summary.setdefault(dataset, {}).setdefault(method, {})
        entry[tissue] = {
            m: subject_interval(group[m].dropna().to_numpy(), seed=seed)
            for m in ("Dice", "HD95_mm", "ASSD_mm", "signed_relative_volume_error")
            if group[m].notna().any()
        }
    for key, group in table.groupby("dataset"):
        dataset = str(key)
        paired = group.pivot_table(index=["subject", "name"], columns="method", values="Dice")
        diff = (paired["synthseg"] - paired["multiotsu_control"]).groupby("name")
        summary[dataset]["paired_Dice_synthseg_minus_control"] = {
            str(tissue): subject_interval(values.to_numpy(), seed=seed) for tissue, values in diff
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthseg-cmd", required=True)
    parser.add_argument("--phase", choices=["development", "external"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seal = require_frozen_protocol()
    cfg = yaml.safe_load(Path("configs/human-tissues.yaml").read_text())
    safe_local_output(args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "external":
        done = args.output / "development-summary.json"
        if not done.exists():
            raise SystemExit("Held-out MRBrainS is scored only after the IBSR development run")
        if (args.output / "external-summary.json").exists():
            raise SystemExit("Held-out cases are scored once; delete nothing, open a new protocol")
    inventory = discover_human(Path(cfg["ibsr_root"]), Path(cfg["mrbrains_root"]))
    selected = [r for r in inventory["subjects"] if r["partition"] == args.phase]
    rows: list[dict[str, Any]] = []
    failures = []
    for record in selected:
        try:
            rows.extend(evaluate(record, args.synthseg_cmd, args.output))
        except (ValueError, OSError, subprocess.CalledProcessError) as exc:
            failures.append({"subject": record["subject"], "reason": str(exc)})
    table = pd.DataFrame(rows)
    table.to_csv(args.output / f"{args.phase}-per-case.csv", index=False)
    write_json(
        args.output / f"{args.phase}-summary.json",
        {
            "phase": args.phase,
            "protocol_seal": seal,
            "soma_version": version("soma-neuro"),
            "requested": len(selected),
            "completed_cases": int(table["subject"].nunique()) if len(table) else 0,
            "failures": failures,
            "cohorts": summarize(table, int(cfg["seed"])) if len(table) else None,
        },
    )


if __name__ == "__main__":
    main()
