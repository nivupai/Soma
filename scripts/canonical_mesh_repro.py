"""Canonical-mesh v1: exact serialized inputs, unchanged FEM, no native meshing."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import homogeneous_series
from soma.source.fem_reference import full_subtraction
from soma.source.mesh_replication import audit_volume, candidate_grid, nearest_distances
from soma.source.noise import average_projector

PROTOCOL_PATH = Path("configs/canonical-mesh-v1.json")
FIXTURE_PATH = Path("configs/mesh-grid-control-v30.json")
PROTOCOL_SHA256 = "5582092498c99f623c27ea92d3edfebcf26a157025a22d526d4527c417365a0b"


def array_hash(value, dtype):
    a = np.ascontiguousarray(value, dtype=dtype)
    header = json.dumps(dict(dtype=a.dtype.str, shape=list(a.shape)), sort_keys=True).encode()
    return hashlib.sha256(header + b"\0" + a.tobytes()).hexdigest()


def load_inputs(protocol_path=PROTOCOL_PATH, fixture_path=FIXTURE_PATH):
    raw = protocol_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Canonical protocol integrity failure")
    protocol = json.loads(raw)
    if (
        hashlib.sha256(Path(protocol["strict_comparator"]).read_bytes()).hexdigest()
        != protocol["strict_comparator_sha256"]
    ):
        raise ValueError("Original strict comparator integrity failure")
    raw_fixture = fixture_path.read_bytes()
    if hashlib.sha256(raw_fixture).hexdigest() != protocol["fixture_sha256"]:
        raise ValueError("Canonical fixture integrity failure")
    fixture = json.loads(raw_fixture)
    if (
        fixture["schema"] != "soma.mesh-grid.diagnostic-fixture/1"
        or fixture["synthetic_only"] is not True
    ):
        raise ValueError("Unsupported synthetic fixture")
    m = fixture["mesh"]
    t, labels = np.asarray(m["tetrahedra"]), np.asarray(m["labels"])
    if not np.issubdtype(t.dtype, np.integer) or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Integer connectivity and labels required")
    arrays = dict(
        vertices_m=np.asarray(m["vertices_m"], dtype="<f8"),
        tetrahedra=t.astype("<i8"),
        labels=labels.astype("<i8"),
        sources_m=np.asarray(fixture["sources_m"], dtype="<f8"),
        sensors_m=np.asarray(fixture["sensors_m"], dtype="<f8"),
        conductivities_S_m=np.asarray(protocol["conductivities_S_m"], dtype="<f8"),
    )
    if any(not np.isfinite(v).all() for v in arrays.values()):
        raise ValueError("Nonfinite physical input")
    counts = protocol["mesh_counts"]
    if (
        arrays["vertices_m"].shape != (counts["nodes"], 3)
        or t.shape != (counts["tetrahedra"], 4)
        or arrays["sources_m"].shape != (counts["sources"], 3)
        or arrays["sensors_m"].shape != (counts["sensors"], 3)
    ):
        raise ValueError("Canonical physical dimensions changed")
    surfaces = [
        Mesh(Points(v["vertices_m"], Frame.MRI), np.asarray(v["faces"]), dict(synthetic=True))
        for v in fixture["surfaces"]
    ]
    quality = audit_volume(arrays["vertices_m"], arrays["tetrahedra"], arrays["labels"], surfaces)
    fingerprints = {
        k: array_hash(v, "<i8" if k in ["tetrahedra", "labels"] else "<f8")
        for k, v in arrays.items()
    }
    for i, surface in enumerate(surfaces):
        fingerprints[f"interface_{i}_vertices"] = array_hash(surface.vertices.xyz, "<f8")
        fingerprints[f"interface_{i}_faces"] = array_hash(surface.faces, "<i8")
    return protocol, arrays, quality, fingerprints


def run():
    protocol, a, q, fingerprints = load_inputs()
    g, diagnostics = full_subtraction(
        a["vertices_m"],
        a["tetrahedra"],
        a["labels"],
        a["sources_m"],
        a["sensors_m"],
        protocol["conductivities_S_m"],
        quadrature=protocol["quadrature"],
    )
    exact = average_projector(len(a["sensors_m"])) @ homogeneous_series(
        a["sources_m"], a["sensors_m"]
    )
    relative = float(np.linalg.norm(g - exact) / np.linalg.norm(exact))
    if (
        not 0 < relative < protocol["analytical_relative_limit"]
        or not 0 <= diagnostics["relative_residual"] < protocol["max_algebraic_residual"]
    ):
        raise ValueError("Canonical physical solver control failed")
    environment = dict(
        system=platform.system(), machine=platform.machine(), python=platform.python_version()
    )
    report = dict(
        schema="soma.mesh-grid.repro/1",
        environment=environment,
        protocol=PROTOCOL_SHA256,
        lead=g.tolist(),
        relative=relative,
        tissue_volumes_m3=q["tissue_volumes_m3"],
        min_mean_ratio=q["min_mean_ratio"],
        boundary_coordinate_max_m=q["boundary_coordinate_max_m"],
        nearest_mm=[
            float(nearest_distances(candidate_grid(s).xyz, np.array([[0.012, 0.023, 0.034]]))[0])
            for s in [30, 20, 15]
        ],
        scope=(
            "canonical-mesh-v1 numerical portability only; native meshing not invoked or validated"
        ),
    )
    return dict(
        schema="soma.canonical-mesh.repro/1",
        experiment=protocol["experiment"],
        version=protocol["version"],
        protocol_sha256=PROTOCOL_SHA256,
        fixture_sha256=protocol["fixture_sha256"],
        physical_fingerprints=fingerprints,
        native_meshing_invoked=False,
        environment=environment,
        solver_diagnostics=diagnostics,
        strict_field_report=report,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(run(), indent=2) + "\n")
