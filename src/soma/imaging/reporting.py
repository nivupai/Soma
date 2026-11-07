"""Reusable bounded MRI report measurements and provenance."""

import hashlib
import resource
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

from soma.core.provenance import manifest, output_directory, sha256, write_json


class ImagingReport:
    def __init__(
        self,
        output: Path,
        parameters: dict[str, Any],
        *,
        seed: int | None = None,
        source: dict[str, Any] | None = None,
    ) -> None:
        self.output = output_directory(output)
        self.parameters, self.seed, self.source = parameters, seed, source or {}
        self.start, self.cpu_start = time.perf_counter(), time.process_time()

    def finish(self, summary: dict[str, Any]) -> dict[str, Any]:
        summary.update(
            {
                "runtime_s": time.perf_counter() - self.start,
                "cpu_s": time.process_time() - self.cpu_start,
                "process_peak_RSS_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / (1024**2 if sys.platform == "darwin" else 1024),
                "RSS_scope": "process high-water including libraries; not incremental allocation",
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
            p.name: sha256(p) for p in self.output.iterdir() if p.is_file()
        }
        write_json(self.output / "manifest.json", metadata)
        return summary
