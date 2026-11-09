"""Reproduce staged diagnostics and read-only readiness, never launch fMRIPrep.

Outputs must not exist. Historical calibration reproduction was run at baseline
8e24b6e before modifications; see README for that separate command.
"""

import json
from pathlib import Path

import yaml

from soma.fmri.null_audit import audit_null
from soma.fmri.preprocessing_setup import readiness


def main() -> None:
    result = audit_null(
        yaml.safe_load(Path("configs/fmri-null-audit.yaml").read_text()),
        Path("reports/milestone141-null-audit"),
    )
    readiness(
        Path("configs/fmri-preprocessing-plan.yaml"),
        Path("reports/milestone141-preprocessing-plan"),
        runtime=json.loads(Path("data/derived/milestone141/runtime.json").read_text()),
        image_manifest=json.loads(
            Path("data/derived/milestone141/image-manifest.json").read_text()
        ),
    )
    print(json.dumps({"rows": result["rows"], "wall_s": result["wall_s"]}))


if __name__ == "__main__":
    main()
