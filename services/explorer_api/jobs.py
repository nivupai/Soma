"""One bounded worker with cooperative cancellation and private atomic receipts."""

import hashlib
import json
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .models import Job, JobRequest


class Jobs:
    def __init__(self, calculate: Callable[[JobRequest], Any], root: Path) -> None:
        self.calculate, self.root = calculate, root
        self.lock = threading.Lock()
        self.items: dict[str, Job] = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="soma-explorer")

    def submit(self, request: JobRequest) -> Job:
        with self.lock:
            if sum(j.status in {"queued", "running"} for j in self.items.values()) >= 2:
                raise ValueError("Job capacity reached (one running, one queued)")
            if len(self.items) >= 100:
                raise ValueError("Session job history limit reached; restart service")
            identity = uuid.uuid4().hex
            job = Job(id=identity, status="queued", progress=0)
            self.items[identity] = job
        self.pool.submit(self.run, identity, request)
        return job.model_copy(deep=True)

    def run(self, identity: str, request: JobRequest) -> None:
        with self.lock:
            job = self.items[identity]
            if job.status == "cancelled":
                return
            job.status, job.progress = "running", 0.15
        try:
            result = self.calculate(request)
            with self.lock:
                if job.status == "cancelled":
                    return
                job.progress = 0.9
                manifest = {
                    "job_id": identity,
                    "kind": request.kind,
                    "parameters": request.model_dump(),
                    "dataset_sha256": result.provenance["input_sha256"],
                    "state": str(result.state),
                    "provenance": result.provenance,
                    "scientific_policy": "descriptive",
                    "limits": {"worker_count": 1, "duration_s": 30, "channels": 1},
                }
                self.root.mkdir(parents=True, exist_ok=True)
                result_text = result.model_dump_json()
                result_temporary = self.root / (identity + ".result.tmp")
                result_temporary.write_text(result_text)
                result_temporary.replace(self.root / (identity + ".result.json"))
                manifest["result_sha256"] = hashlib.sha256(result_text.encode()).hexdigest()
                manifest["result_artifact_id"] = identity
                temporary = self.root / (identity + ".tmp")
                temporary.write_text(json.dumps(manifest))
                temporary.replace(self.root / (identity + ".json"))
                job.result, job.manifest = result, manifest
                job.status, job.progress = "completed", 1
        except Exception:
            with self.lock:
                if job.status != "cancelled":
                    job.status, job.error = (
                        "failed",
                        "Analysis failed; inspect selected inputs and limits",
                    )

    def get(self, identity: str) -> Job:
        with self.lock:
            return self.items[identity].model_copy(deep=True)

    def cancel(self, identity: str) -> Job:
        with self.lock:
            job = self.items[identity]
            if job.status in {"queued", "running"}:
                job.status = "cancelled"
            return job.model_copy(deep=True)

    def close(self) -> None:
        self.pool.shutdown(wait=True, cancel_futures=True)
