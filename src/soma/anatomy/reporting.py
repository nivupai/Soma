"""Anatomical study receipts including nested transforms and physical cache stages."""

import hashlib
import resource
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any

from soma.core.provenance import manifest, output_directory, sha256, write_json


class AnatomyReport:
    def __init__(
        self,
        output: Path,
        parameters: dict[str, Any],
        source: dict[str, Any] | None = None,
        seed: int = 42,
    ) -> None:
        self.output = output_directory(output)
        self.parameters = parameters
        self.source = source or {}
        self.seed = seed
        self.start = time.perf_counter()
        self.cpu = time.process_time()
        self.stages: dict[str, Any] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start, cpu = time.perf_counter(), time.process_time()
        try:
            yield
        finally:
            self.stages[name] = {
                "wall_s": time.perf_counter() - start,
                "cpu_s": time.process_time() - cpu,
            }

    def finish(self, summary: dict[str, Any]) -> dict[str, Any]:
        summary.update(
            {
                "wall_s": time.perf_counter() - self.start,
                "cpu_s": time.process_time() - self.cpu,
                "stages": self.stages,
                "process_peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / (1024**2 if sys.platform == "darwin" else 1024),
                "memory_scope": (
                    "process high-water including libraries, not incremental allocation"
                ),
            }
        )
        write_json(self.output / "summary.json", summary)
        metadata = manifest(self.source, self.parameters, {"output": str(self.output)}, self.seed)
        metadata["libraries"].update(
            {name: version(name) for name in ("nibabel", "SimpleITK", "scikit-image")}
        )
        metadata["source_tree_sha256"] = hashlib.sha256(
            b"".join(
                str(p).encode() + p.read_bytes() for p in sorted(Path("src/soma").rglob("*.py"))
            )
        ).hexdigest()
        metadata["outputs_sha256"] = {
            str(p.relative_to(self.output)): sha256(p)
            for p in self.output.rglob("*")
            if p.is_file()
        }
        write_json(self.output / "manifest.json", metadata)
        return summary
