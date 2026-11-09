"""Final frozen execution; missing real derivatives must return nonzero, not success."""

import os
import subprocess
from pathlib import Path

from soma.core.provenance import write_json


def main() -> None:
    environment = {
        **os.environ,
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": "/private/tmp/soma-mpl",
        "XDG_CACHE_HOME": "/private/tmp/soma-cache",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "LOKY_MAX_CPU_COUNT": "1",
        "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": "1",
    }
    commands = [
        (
            "audit",
            [
                ".venv/bin/soma",
                "fmri",
                "audit-preproc",
                "--config",
                "configs/fmri-audit.yaml",
                "--output",
                "reports/milestone14-audit",
            ],
            1,
        ),
        (
            "pilot",
            [
                ".venv/bin/soma",
                "fmri",
                "pilot-retest",
                "--config",
                "configs/retest-pilot.yaml",
                "--output",
                "reports/milestone14-pilot",
            ],
            1,
        ),
        (
            "cohort",
            [
                ".venv/bin/soma",
                "fmri",
                "cohort-retest",
                "--config",
                "configs/retest-cohort.yaml",
                "--output",
                "reports/milestone14-cohort",
            ],
            1,
        ),
        (
            "sensitivity",
            [
                ".venv/bin/soma",
                "fmri",
                "sensitivity",
                "--config",
                "configs/fmri-sensitivity.yaml",
                "--output",
                "reports/milestone14-sensitivity",
            ],
            1,
        ),
        ("laboratory", [".venv/bin/python", "experiments/milestone14/laboratory.py"], 0),
        (
            "calibration",
            [
                ".venv/bin/soma",
                "fmri",
                "calibrate",
                "--config",
                "configs/fmri-calibration-validation.yaml",
                "--output",
                "reports/milestone14-calibration",
            ],
            0,
        ),
    ]
    rows = []
    for name, command, expected in commands:
        log = Path("/private/tmp") / ("soma-m14-final-" + name + ".log")
        with log.open("w") as stream:
            result = subprocess.run(
                command, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=False
            )
        rows.append(
            {
                "workflow": name,
                "command": command,
                "returncode": result.returncode,
                "expected": expected,
            }
        )
        if result.returncode != expected:
            raise RuntimeError(
                "Unexpected final workflow result: " + name + "; inspect " + str(log)
            )
    write_json(Path("data/derived/milestone14/final-execution.json"), rows)
    print("Final synthetic workflows complete; real preprocessing/retest correctly unavailable.")


if __name__ == "__main__":
    main()
