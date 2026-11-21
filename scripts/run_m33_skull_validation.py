"""M33 skull benchmark: T1-only baseline head surfaces vs independent CT bone (SynthRAD2023).

Refuses to score until docs/MILESTONE33_SKULL_PROTOCOL.md is sealed in
configs/m33-skull-freeze.json (owner-run ``scripts.seal_m33_skull``). Participant-derived
outputs stay in ignored local storage; only aggregates may ever be committed.

    python -m scripts.run_m33_skull_validation \
        --synthseg-cmd "/abs/run-synthseg.sh --i {input} --o {output} --robust --threads 8" \
        --data-root /abs/data/external/synthrad2023/brain --output reports/milestone33/skull
"""

import argparse
import json
import re
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from scripts.run_m33_segmentation import run_synthseg
from soma.anatomy.t1_skull import T1SkullParameters, estimate_t1_skull
from soma.benchmarks.ct_skull import (
    PRIMARY_BONE_HU,
    SENSITIVITY_BONE_HU,
    CTSkullParameters,
    FlagThresholds,
    RegionRule,
    ct_truth,
    exclusion_flags,
    score_case,
)
from soma.core.provenance import sha256, write_json
from soma.datasets.human_mri import safe_local_output
from soma.imaging.nifti import load_nifti
from soma.pipeline.synthseg import load_synthseg
from soma.validation.cohort import subject_interval

PROTOCOL = Path("docs/MILESTONE33_SKULL_PROTOCOL.md")
FREEZE = Path("configs/m33-skull-freeze.json")
SEED = 11042
CASE_ID = re.compile(r"^\d[A-Z]([A-Z])\d+$")
# Decision rule as written in the protocol (proposed values; sealed with it).
MINIMUM_EVALUABLE_CASES = 15
LIMITS_MM = {
    "inner_skull": {"mean_abs_mm": 2.0, "HD95_mm": 5.0},
    "outer_scalp": {"mean_abs_mm": 2.0, "HD95_mm": 5.0},
    "outer_skull": {"mean_abs_mm": 3.0, "HD95_mm": 7.0},
}
THICKNESS_LIMIT_MM = 2.0


def require_frozen_protocol(
    protocol: Path | None = None, freeze: Path | None = None
) -> dict[str, Any]:
    protocol, freeze = protocol or PROTOCOL, freeze or FREEZE
    if not freeze.exists():
        raise SystemExit("M33 skull protocol not frozen: owner approval and seal required")
    seal = json.loads(freeze.read_text())
    if seal.get("protocol_sha256") != sha256(protocol) or seal.get("owner_approved") is not True:
        raise SystemExit("M33 skull protocol seal mismatch or not owner-approved; scoring refused")
    return dict(seal)


def discover(root: Path) -> list[Path]:
    cases = sorted(
        d
        for d in root.iterdir()
        if d.is_dir() and all((d / f"{n}.nii.gz").is_file() for n in ("mr", "ct", "mask"))
    )
    if not cases:
        raise SystemExit(f"No SynthRAD2023 brain cases (mr/ct/mask.nii.gz) under {root}")
    return cases


def centre(case: str) -> str:
    match = CASE_ID.match(case)
    return match.group(1) if match else "unknown"


def evaluate_case(
    case_dir: Path, command: str, output: Path, *, check_nesting: bool
) -> dict[str, Any]:
    case = case_dir.name
    cached = output / "cases" / case / "skull-metrics.json"
    if cached.exists():  # resume: a finished case is never recomputed or re-scored
        return dict(json.loads(cached.read_text()))
    t1 = load_nifti(case_dir / "mr.nii.gz")
    ct = load_nifti(case_dir / "ct.nii.gz")
    mask = load_nifti(case_dir / "mask.nii.gz", kind="labels")
    if not (t1.same_grid(ct) and ct.same_grid(mask)):
        raise ValueError("SynthRAD MR/CT/mask grids differ; the paired-grid premise fails")
    cache = output / "cases" / case
    synth = load_synthseg(run_synthseg(command, case_dir / "mr.nii.gz", cache))
    estimate = estimate_t1_skull(
        t1, synth, parameters=T1SkullParameters(), check_nesting=check_nesting
    )
    truths = {
        hu: ct_truth(ct, mask, parameters=CTSkullParameters(bone_hu=hu))
        for hu in (PRIMARY_BONE_HU, *SENSITIVITY_BONE_HU)
    }
    primary = truths[PRIMARY_BONE_HU]
    region = RegionRule().fit(primary.masks["inner_skull"])
    flags = exclusion_flags(ct, mask, primary, region, t1=t1, thresholds=FlagThresholds())
    result = {
        "case": case,
        "centre": centre(case),
        "estimator": {
            "provenance": estimate.provenance,
            "nesting": None
            if estimate.nesting is None
            else {k: v for k, v in estimate.nesting.items() if k != "quality"},
        },
        "truth": {str(hu): t.provenance for hu, t in truths.items()},
        "flags": flags,
        "scores": {
            str(hu): score_case(estimate.meshes, estimate.masks, truth, region, seed=SEED)
            for hu, truth in truths.items()
        },
    }
    write_json(cache / "skull-metrics.json", result)
    return result


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for hu, scores in result["scores"].items():
        base = {
            "case": result["case"],
            "centre": result["centre"],
            "flagged": bool(result["flags"]["any"]),
            "bone_hu": float(hu),
        }
        for boundary, metric in scores["boundaries"].items():
            for name in ("signed_mean_mm", "mean_abs_mm", "HD95_mm"):
                out.append({**base, "boundary": boundary, "metric": name, "value": metric[name]})
        for name in ("mean_error_mm", "mean_abs_error_mm"):
            out.append(
                {
                    **base,
                    "boundary": "thickness",
                    "metric": name,
                    "value": scores["thickness"][name],
                }
            )
    return out


def intervals(table: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    groups: dict[str, dict[str, list[float]]] = {}
    for row in table:
        groups.setdefault(row["boundary"], {}).setdefault(row["metric"], []).append(row["value"])
    return {
        b: {m: subject_interval(np.asarray(v), seed=seed) for m, v in metrics.items()}
        for b, metrics in groups.items()
    }


def decide(primary: dict[str, Any], n: int) -> dict[str, Any]:
    def passes(boundary: str) -> bool:
        stats = primary.get(boundary, {})
        return all(
            stats.get(metric, {}).get("CI95") is not None
            and stats[metric]["mean"] <= limit
            and stats[metric]["CI95"][1] < limit
            for metric, limit in LIMITS_MM[boundary].items()
        )

    thickness = primary.get("thickness", {}).get("mean_error_mm", {})
    thickness_ok = thickness.get("CI95") is not None and all(
        abs(x) < THICKNESS_LIMIT_MM for x in thickness["CI95"]
    )
    checks = {
        "enough_cases": n >= MINIMUM_EVALUABLE_CASES,
        "inner_skull": passes("inner_skull"),
        "outer_scalp": passes("outer_scalp"),
        "outer_skull": passes("outer_skull"),
        "thickness": thickness_ok,
    }
    if checks["enough_cases"] and checks["inner_skull"] and checks["outer_scalp"]:
        status = "VALIDATED" if checks["outer_skull"] and checks["thickness"] else "QC_ONLY"
    else:
        status = "NOT_READY"
    return {
        "readiness": status,
        "scope": "T1-only geometric baseline method only; not any other head model",
        "checks": checks,
        "limits_mm": LIMITS_MM,
        "thickness_limit_mm": THICKNESS_LIMIT_MM,
        "minimum_evaluable_cases": MINIMUM_EVALUABLE_CASES,
    }


def summarize(results: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    table = [r for result in results for r in rows(result)]
    primary_rows = [r for r in table if r["bone_hu"] == PRIMARY_BONE_HU and not r["flagged"]]
    primary = intervals(primary_rows, seed) if primary_rows else {}
    evaluable = len({r["case"] for r in primary_rows})
    by_centre = {
        c: intervals([r for r in primary_rows if r["centre"] == c], seed)
        for c in sorted({r["centre"] for r in primary_rows})
    }
    sensitivity = {
        "all_cases_including_flagged": intervals(
            [r for r in table if r["bone_hu"] == PRIMARY_BONE_HU], seed
        ),
        **{
            f"bone_hu_{int(hu)}": intervals(
                [r for r in table if r["bone_hu"] == hu and not r["flagged"]], seed
            )
            for hu in SENSITIVITY_BONE_HU
            if any(r["bone_hu"] == hu and not r["flagged"] for r in table)
        },
    }
    return {
        "primary": {"bone_hu": PRIMARY_BONE_HU, "evaluable_cases": evaluable, "metrics": primary},
        "by_centre": by_centre,
        "sensitivity": sensitivity,
        "flagged_cases": {
            r["case"]: {
                k: v for k, v in r["flags"].items() if isinstance(v, dict) and v.get("flag")
            }
            for r in results
            if r["flags"]["any"]
        },
        "decision": decide(primary, evaluable),
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthseg-cmd", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument(
        "--check-nesting",
        action="store_true",
        help="run full nested_boundaries on each estimate (slow on 1 mm heads)",
    )
    args = parser.parse_args(argv)
    seal = require_frozen_protocol()
    safe_local_output(args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "cohort-summary.json").exists():
        raise SystemExit("Cohort already scored; a rerun needs a new protocol version")
    cases = discover(args.data_root.resolve())
    if args.cases:
        cases = [c for c in cases if c.name in set(args.cases)]
    results, failures = [], []
    for case_dir in cases:
        try:
            results.append(
                evaluate_case(
                    case_dir, args.synthseg_cmd, args.output, check_nesting=args.check_nesting
                )
            )
        except Exception as exc:  # every failure is reported per case, never hidden
            failures.append({"case": case_dir.name, "reason": f"{type(exc).__name__}: {exc}"})
    write_json(
        args.output / "cohort-summary.json",
        {
            "protocol_seal": seal,
            "soma_version": version("soma-neuro"),
            "dataset": "SynthRAD2023 Task 1 brain (CC BY-NC 4.0); aggregates only",
            "requested": len(cases),
            "completed_cases": len(results),
            "failures": failures,
            "bootstrap": {"seed": SEED, "repetitions": 2000, "unit": "subject"},
            "cohort": summarize(results, SEED) if results else None,
        },
    )


if __name__ == "__main__":
    main()
