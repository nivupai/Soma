"""Owner-run seal for the M33 skull protocol. Run once, by the project owner, after review.

python -m scripts.seal_m33_skull_v31 --approved-by "<owner name>"
"""

import argparse
import datetime
import json
from pathlib import Path

from soma.core.provenance import sha256

PROTOCOL = Path("docs/MILESTONE33_SKULL_PROTOCOL_V31.md")
FREEZE = Path("configs/m33-skull-v31-freeze.json")
MODEL = Path("reports/milestone33/skull-dev-crop/refine-model-v3.1-final.pkl")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    if not MODEL.exists():
        raise SystemExit("Train the v3.1 model first (scripts.dev_m33_crop evaluate)")
    if FREEZE.exists():
        raise SystemExit("Already sealed; a change needs a new protocol version")
    FREEZE.write_text(
        json.dumps(
            {
                "protocol": str(PROTOCOL),
                "protocol_sha256": sha256(PROTOCOL),
                "owner_approved": True,
                "model": str(MODEL),
                "model_sha256": sha256(MODEL),
                "approved_by": args.approved_by,
                "frozen_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "held_out_metrics_inspected": False,
                "development_cases_inspected": True,
                "dataset": "SynthRAD2023 Task 1 brain, CC BY-NC 4.0, aggregates only",
                "synthseg": {
                    "version": "SynthSeg-robust 2.0",
                    "git_commit": "2a2aa3bbfccb83f8253a51ca8b329b9938a2646d",
                    "synthseg_robust_2.0.h5_sha256": (
                        "7bc30bf5c3d204f20c4a6cb5a283aedbcab6af1de927cda783f59b67d19cb01c"
                    ),
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Sealed {PROTOCOL} -> {FREEZE}")


if __name__ == "__main__":
    main()
