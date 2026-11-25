"""Resumable, memory-safe job queue for the M33 skull work, independent of any Claude session.

Each task is a shell command plus a "done" file. Finished tasks are never rerun, so the queue
can be stopped, killed or interrupted by a reboot and simply started again. Phases run in
order; inside a phase at most ``--workers`` tasks run at once (default 2). SynthSeg is further
serialised by the lock in its launcher. A task that fails twice is recorded as failed and the
queue moves on. Progress is written to ``reports/soma-queue/status.json`` for ``soma-status``.

    .venv/bin/python -m scripts.soma_queue            # run (normally via scripts/soma-queue)
"""

import argparse
import datetime
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "reports" / "soma-queue"
PY = shlex.quote(sys.executable)
DEV_SPLIT = ROOT / "configs" / "m33-skull-v2-split.json"
HN = Path("/Volumes/YOTUO/soma-data/synthrad2025/hn")
CROP = ROOT / "reports/milestone33/skull-dev-crop"
V31 = ROOT / "reports/milestone33/skull-v31"
SEAL_V31 = ROOT / "configs/m33-skull-v31-freeze.json"


@dataclass
class Task:
    id: str
    cmd: str
    done: Path


@dataclass
class Phase:
    name: str
    tasks: list[Task]
    gate: Path | None = None  # phase waits until this file exists (e.g. the owner's seal)
    gate_message: str = ""
    attempts: dict[str, int] = field(default_factory=dict)


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def hn_cases() -> list[str]:
    if not HN.exists():
        return []
    return sorted(
        p.name
        for p in HN.iterdir()
        if all((p / f).exists() for f in ("mr.nii.gz", "ct.nii.gz", "mask.nii.gz"))
    )


def phases() -> list[Phase]:
    split = json.loads(DEV_SPLIT.read_text())
    dev = sorted(split["development"])
    held_out = sorted(split["held_out"])
    run = f"cd {shlex.quote(str(ROOT))} && PYTHONPATH=. {PY} -m"
    return [
        Phase(
            "1 development check: crop + SynthSeg + watershed (60 cases)",
            [
                Task(
                    f"dev:{c}",
                    f"{run} scripts.dev_m33_crop prepare --cases {c}",
                    CROP / "cases" / c / "refine-features.npz",
                )
                for c in dev
            ],
        ),
        Phase(
            "2 development check: train and score (leave-one-centre-out)",
            [
                Task(
                    "dev:evaluate",
                    f"{run} scripts.dev_m33_crop evaluate",
                    CROP / "refine-model-v3.1-final.pkl",
                )
            ],
        ),
        Phase(
            "3 CT-only exclusion flags (test cases)",
            [
                Task(
                    f"flags:{c}",
                    f"{run} scripts.flags_m33_v3 {c}",
                    ROOT / "reports/milestone33/skull-v3/flags" / f"{c}.json",
                )
                for c in hn_cases()
            ],
        ),
        Phase(
            "4 final test: v3.1 per case (scored once)",
            [
                Task(
                    f"test:{c}",
                    f"{run} scripts.run_m33_skull_v31 --case {c}",
                    V31 / "cases" / c / "skull-v3-metrics.json",
                )
                for c in hn_cases()
            ],
            gate=SEAL_V31,
            gate_message="waiting for the owner to seal protocol v3.1 "
            "(.venv/bin/python -m scripts.seal_m33_skull_v31 --approved-by <name>)",
        ),
        Phase(
            "5 final test: aggregate",
            [
                Task(
                    "test:aggregate",
                    f"{run} scripts.run_m33_skull_v31 --aggregate",
                    V31 / "cohort-summary.json",
                )
            ],
            gate=SEAL_V31,
        ),
        Phase(
            "6 bigger training set: prepare the 120 finished v2 test cases",
            [
                Task(
                    f"train180:{c}",
                    f"{run} scripts.dev_m33_crop prepare --pool all --cases {c}",
                    CROP / "cases" / c / "refine-features.npz",
                )
                for c in held_out
            ],
        ),
        Phase(
            "7 bigger training set: leave-one-centre-out on 180 cases + v3.2 model",
            [
                Task(
                    "train180:evaluate",
                    f"{run} scripts.dev_m33_crop evaluate --pool all",
                    CROP / "refine-model-v3.2-final.pkl",
                )
            ],
        ),
    ]


def newest_done(all_phases: list[Phase], fallback: str) -> str:
    """Most recent finish time of any task, including work done by earlier hand-started runs."""
    times = [t.done.stat().st_mtime for p in all_phases for t in p.tasks if t.done.exists()]
    if not times:
        return fallback
    latest = datetime.datetime.fromtimestamp(max(times)).astimezone().isoformat(timespec="seconds")
    return max(latest, fallback)


def failed_marker(task: Task) -> Path:
    return STATE / "failed" / (task.id.replace(":", "_") + ".json")


def write_status(status: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = STATE / "status.tmp"
    tmp.write_text(json.dumps(status, indent=1))
    os.replace(tmp, STATE / "status.json")


def log(message: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "queue.log", "a") as f:
        f.write(f"{now()} {message}\n")


def legacy_running() -> bool:
    """Earlier hand-started chains: wait for them instead of duplicating their work."""
    return (
        subprocess.run(["pgrep", "-f", "crop_chain.sh|v3_chain.sh"], capture_output=True).returncode
        == 0
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    (STATE / "failed").mkdir(parents=True, exist_ok=True)
    (STATE / "logs").mkdir(parents=True, exist_ok=True)
    last_progress = now()
    log(f"queue started (pid {os.getpid()}, workers {args.workers})")
    all_phases = phases()
    for index, phase in enumerate(all_phases):
        while True:
            todo = [t for t in phase.tasks if not t.done.exists() and not failed_marker(t).exists()]
            waiting = ""
            if legacy_running():
                waiting = "an earlier hand-started run is still going; waiting for it to finish"
            elif phase.gate is not None and not phase.gate.exists() and todo:
                waiting = phase.gate_message
            status = {
                "pid": os.getpid(),
                "updated_at": now(),
                "last_progress_at": newest_done(all_phases, last_progress),
                "phase": phase.name,
                "phase_index": index + 1,
                "phases_total": len(all_phases),
                "waiting_for": waiting,
                "phases": [
                    {
                        "name": p.name,
                        "total": len(p.tasks),
                        "done": sum(t.done.exists() for t in p.tasks),
                        "failed": sum(failed_marker(t).exists() for t in p.tasks),
                    }
                    for p in all_phases
                ],
                "running": [],
            }
            if not todo:
                break
            if waiting:
                write_status(status)
                time.sleep(60)
                continue
            batch = todo[: args.workers]
            procs = []
            for task in batch:
                out = open(STATE / "logs" / (task.id.replace(":", "_") + ".log"), "a")  # noqa: SIM115
                out.write(f"\n=== {now()} {task.cmd}\n")
                out.flush()
                procs.append(
                    (
                        task,
                        subprocess.Popen(task.cmd, shell=True, stdout=out, stderr=out),
                        out,
                        now(),
                    )
                )
                log(f"start {task.id}")
            status["running"] = [{"task": t.id, "started_at": s} for t, _, _, s in procs]
            write_status(status)
            while any(p.poll() is None for _, p, _, _ in procs):
                status["updated_at"] = now()
                write_status(status)
                time.sleep(30)
            for task, proc, out, _ in procs:
                out.close()
                if task.done.exists():
                    last_progress = now()
                    log(f"done {task.id}")
                else:
                    tries = phase.attempts.get(task.id, 0) + 1
                    phase.attempts[task.id] = tries
                    log(f"FAIL {task.id} (exit {proc.returncode}, attempt {tries})")
                    if tries >= 2:
                        failed_marker(task).write_text(
                            json.dumps({"exit": proc.returncode, "at": now(), "log": out.name})
                        )
                        if task.id.startswith("test:"):
                            marker = V31 / "cases" / task.id.split(":", 1)[1] / "FAILED.json"
                            marker.parent.mkdir(parents=True, exist_ok=True)
                            marker.write_text(json.dumps({"reason": f"exit {proc.returncode}"}))
                        last_progress = now()
        log(f"phase complete: {phase.name}")
    final = {
        "pid": os.getpid(),
        "updated_at": now(),
        "last_progress_at": last_progress,
        "phase": "all phases complete",
        "phase_index": len(all_phases),
        "phases_total": len(all_phases),
        "waiting_for": "",
        "running": [],
        "finished": True,
        "phases": [
            {
                "name": p.name,
                "total": len(p.tasks),
                "done": sum(t.done.exists() for t in p.tasks),
                "failed": sum(failed_marker(t).exists() for t in p.tasks),
            }
            for p in all_phases
        ],
    }
    write_status(final)
    log("all phases complete")


if __name__ == "__main__":
    main()
