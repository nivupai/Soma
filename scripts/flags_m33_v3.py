"""CT-only v2 exclusion flags for one SynthRAD2025 HN test case (no skull model, no scoring)."""

import json
import sys
from pathlib import Path

from scripts.run_m33_skull_v3 import load
from soma.benchmarks.ct_skull import (
    FLAGS_V2,
    CTSkullParameters,
    RegionRule,
    ct_truth,
    exclusion_flags,
)

DATA = Path("/Volumes/YOTUO/soma-data/synthrad2025/hn")
OUT = Path("reports/milestone33/skull-v3/flags")

if __name__ == "__main__":
    case = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    ct = load(DATA / case / "ct.nii.gz")
    mask = load(DATA / case / "mask.nii.gz", "labels")
    t1 = load(DATA / case / "mr.nii.gz")
    truth = ct_truth(ct, mask, parameters=CTSkullParameters())
    region = RegionRule().fit(truth.masks["inner_skull"])
    flags = exclusion_flags(ct, mask, truth, region, t1=t1, thresholds=FLAGS_V2)
    summary = {k: (v.get("flag") if isinstance(v, dict) else v) for k, v in flags.items()}
    summary.pop("thresholds", None)
    (OUT / f"{case}.json").write_text(json.dumps(summary))
