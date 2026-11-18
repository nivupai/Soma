"""Separate canonical gate; reuse the frozen original elementwise comparator."""

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np

from scripts.canonical_mesh_repro import PROTOCOL_SHA256, load_inputs
from scripts.compare_mesh_grids import compare as original_strict_compare


def compare(root):
    paths = sorted(Path(root).glob("*/canonical-mesh-v1.json"))
    if len(paths) != 4:
        raise ValueError("Four independent canonical platform reports required")
    protocol, _, _, expected = load_inputs()
    reports = [json.loads(p.read_text()) for p in paths]
    with tempfile.TemporaryDirectory(prefix="soma-canonical-comparison-") as name:
        temporary = Path(name)
        for path, r in zip(paths, reports, strict=True):
            if (
                r.get("schema") != "soma.canonical-mesh.repro/1"
                or r.get("experiment") != protocol["experiment"]
                or r.get("version") != protocol["version"]
                or r.get("protocol_sha256") != PROTOCOL_SHA256
                or r.get("fixture_sha256") != protocol["fixture_sha256"]
                or r.get("physical_fingerprints") != expected
                or r.get("native_meshing_invoked") is not False
            ):
                raise ValueError("Canonical identity or exact physical fingerprint mismatch")
            d = r["solver_diagnostics"]
            if (
                d["units"] != protocol["field_units"]
                or d["frame"] != protocol["frame"]
                or d["quadrature"] != protocol["quadrature"]
                or d["source_order"] != protocol["source_order"]
                or d["reference"] != protocol["reference"]
                or d["solver_version"] != "12.0.2"
            ):
                raise ValueError("Canonical solver physical contract mismatch")
            field = r["strict_field_report"]
            if field["environment"] != r["environment"] or field["protocol"] != PROTOCOL_SHA256:
                raise ValueError("Canonical field provenance mismatch")
            if r["solver_diagnostics"]["relative_residual"] >= protocol["max_algebraic_residual"]:
                raise ValueError("Canonical algebraic residual failed")
            folder = temporary / path.parent.name
            folder.mkdir()
            (folder / "mesh-grid-synthetic.json").write_text(json.dumps(field))
        # Original coverage, units-compatible physical checks, and ALL 192 entries.
        result = original_strict_compare(temporary)
    baseline = np.array(reports[0]["strict_field_report"]["lead"])
    differences = []
    for r in reports:
        field = np.array(r["strict_field_report"]["lead"])
        delta = np.abs(field - baseline)
        differences.append(
            dict(
                environment=r["environment"],
                relative=float(np.linalg.norm(delta) / np.linalg.norm(baseline)),
                max_absolute_V_per_Am=float(delta.max()),
                failed_entries=int(np.sum(delta > 0.01 + 0.02 * np.abs(baseline))),
            )
        )
    return dict(
        schema="soma.canonical-mesh.comparison/1",
        experiment=protocol["experiment"],
        version=protocol["version"],
        all_passed=True,
        reports=4,
        protocol_sha256=PROTOCOL_SHA256,
        fixture_sha256=protocol["fixture_sha256"],
        rtol=0.02,
        atol_V_per_Am=0.01,
        physical_fingerprints_verified=True,
        original_comparator=result,
        platform_differences=differences,
        native_mesh_reproducibility="NOT_ESTABLISHED_SEPARATE_FAILED_NATIVE_GATE",
        release_gate_decision="NOT_AUTHORIZED",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(compare(a.root), indent=2) + "\n")
