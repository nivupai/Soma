"""Summarize actual runner causal controls without changing the M30 gate."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial.distance import cdist

from scripts.diagnose_mesh_grid_entries import diagnose


def difference(actual, reference):
    a, b = np.asarray(actual), np.asarray(reference)
    if a.shape != b.shape or not np.isfinite([a, b]).all():
        raise ValueError("Incompatible numerical operands")
    return dict(
        relative=float(np.linalg.norm(a - b) / np.linalg.norm(b)),
        maximum_absolute=float(np.max(np.abs(a - b))),
    )


def sparse_matrix(c):
    a = c["stiffness"]
    return csr_matrix((a["data"], a["indices"], a["indptr"]), shape=a["shape"]).toarray()


def summarize(root, output):
    paths = sorted(root.glob("*/mesh-grid-diagnostic.json"))
    if len(paths) != 4:
        raise ValueError("All four actual causal runner reports required")
    reports = [(p.parent.name, json.loads(p.read_text())) for p in paths]
    reference_name, reference = reports[0]
    controls = []
    arithmetic = []
    mesh_pairs = []
    for name, d in reports:
        native = d["controls"]["native"]
        original = json.loads((root / name / "mesh-grid-synthetic.json").read_text())
        if not np.array_equal(native["lead"], original["lead"]):
            raise ValueError("Instrumentation changed the original native field")
        if d["fixture_sha256"] != reference["fixture_sha256"]:
            raise ValueError("Different serialized diagnostic fixture")
        for variant, c in d["controls"].items():
            b = reference["controls"][variant]
            row = dict(
                platform=name,
                python=d["environment"]["python"],
                variant=variant,
                reference_platform=reference_name,
            )
            if "lead" not in c or "lead" not in b:
                row.update(status="FAILED", reason=c.get("reason", b.get("reason")))
                controls.append(row)
                continue
            x, y = np.asarray(c["lead"]), np.asarray(b["lead"])
            row.update(
                status="computed",
                **difference(x, y),
                failed_entries=int(np.sum(np.abs(x - y) > 0.01 + 0.02 * np.abs(y))),
                dtype=c["dtype"],
                residual=c["diagnostics"]["relative_residual"],
                nodes=c["diagnostics"]["nodes"],
                elements=c["diagnostics"]["elements"],
                canonical_mesh_hash=c.get("canonical_mesh_hash"),
                mesh_hash=c["diagnostics"]["mesh_hash"],
                input_surface_hash=c.get("surface_hash"),
            )
            controls.append(row)
            if variant.startswith("shared_mesh") and variant != "shared_mesh_reordered":
                arithmetic.append(
                    dict(
                        platform=name,
                        variant=variant,
                        stiffness=difference(sparse_matrix(c), sparse_matrix(b)),
                        RHS=difference(c["rhs_reduced"], b["rhs_reduced"]),
                    )
                )
            if variant in [
                "native",
                "canonical_input",
                "shared_input",
                "reproducible_option",
                "random_factor_zero",
                "alternate_seed",
            ]:
                av, bv = np.array(c["mesh"]["vertices_m"]), np.array(b["mesh"]["vertices_m"])
                distances = cdist(av, bv)
                mesh_pairs.append(
                    dict(
                        platform=name,
                        variant=variant,
                        raw_mesh_identical=c["mesh"] == b["mesh"],
                        numbering_independent_mesh_identical=c["canonical_mesh_hash"]
                        == b["canonical_mesh_hash"],
                        maximum_bidirectional_vertex_distance_m=float(
                            max(distances.min(axis=0).max(), distances.min(axis=1).max())
                        ),
                        tissue_counts=c["quality"]["tissue_counts"],
                        boundary_coordinate_max_m=c["quality"]["boundary_coordinate_max_m"],
                        material_interfaces_verified=c["quality"][
                            "interface_connectivity_verified"
                        ],
                        actual_options=c["options"],
                    )
                )
    output.mkdir(parents=True, exist_ok=True)
    columns = sorted(set().union(*(r.keys() for r in controls)))
    with (output / "control-comparisons.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(controls)
    result = dict(
        schema="soma.mesh-grid.causal-summary/1",
        historical_results_modified=False,
        frozen_rtol=0.02,
        frozen_atol_V_per_Am=0.01,
        fixture_sha256=reference["fixture_sha256"],
        report_hashes={
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        environments={n: d["environment"] for n, d in reports},
        input_coordinates={
            n: dict(
                sources_identical=np.array_equal(d["sources_m"], reference["sources_m"]),
                sensors_identical=np.array_equal(d["sensors_m"], reference["sensors_m"]),
                sensor_maximum_absolute_difference_m=float(
                    np.max(np.abs(np.asarray(d["sensors_m"]) - reference["sensors_m"]))
                ),
                original_surface_hash=d["original_surface_hash"],
                canonical_surface_hash=d["canonical_surface_hash"],
                shared_sources_identical=(
                    np.array_equal(d["shared_sources_m"], reference["shared_sources_m"])
                    if "shared_sources_m" in d and "shared_sources_m" in reference
                    else None
                ),
                shared_sensors_identical=(
                    np.array_equal(d["shared_sensors_m"], reference["shared_sensors_m"])
                    if "shared_sensors_m" in d and "shared_sensors_m" in reference
                    else None
                ),
                C_runtime_random_sequence=d.get("C_runtime_random_sequence"),
            )
            for n, d in reports
        },
        control_comparisons=controls,
        mesh_pairs=mesh_pairs,
        shared_mesh_arithmetic=arithmetic,
    )
    (output / "causal-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    diagnose(root, output / "native-entry-audit")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    summarize(a.root, a.output)
