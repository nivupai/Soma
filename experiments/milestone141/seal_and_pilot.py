"""Seal final evidence/policy before asking the existing human derivative gate.

Does not run preprocessing. Refuses to overwrite an existing policy seal.
"""

import hashlib
import json
from pathlib import Path

from soma.fmri.audit_workflows import pilot_retest
from soma.pipeline.cache import source_hash


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    policy = Path("configs/fmri-inference-policy.yaml")
    seal = {
        "before_new_human_contrasts": True,
        "files_sha256": {str(policy): sha(policy)},
        "calibration_summary_sha256": sha(Path("reports/milestone141-null-audit/summary.json")),
        "source_tree_sha256": source_hash(),
    }
    with Path("configs/milestone141-policy-freeze.json").open("x") as stream:
        json.dump(seal, stream, indent=2)
        stream.write("\n")
    result = pilot_retest(
        Path("configs/retest-pilot.yaml"), Path("reports/milestone141-human-pilot")
    )
    print(json.dumps({"status": result["status"], "completed": result["subjects_completed"]}))


if __name__ == "__main__":
    main()
