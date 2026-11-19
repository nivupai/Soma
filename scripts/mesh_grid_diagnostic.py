"""Post-M30 causal controls; retain native fields and exact shared-mesh arithmetic."""

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from unittest.mock import patch

import numpy as np
import scipy
from threadpoolctl import threadpool_info

from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import sensors
from soma.source.fem_reference import full_subtraction
from soma.source.mesh_replication import audit_volume, boundaries, gmsh_mesh

FIXTURE = Path("configs/mesh-grid-control-v30.json")


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def canonical_mesh(v, t, labels):
    """Remove numbering, row and positive local-orientation permutation differences."""
    v = np.asarray(v, float).copy()
    v[v == 0] = 0  # Normalize signed zero, never round physical coordinates.
    order = np.lexsort(v.T[::-1])
    inverse = np.empty(len(order), int)
    inverse[order] = np.arange(len(order))
    v = v[order]
    t = np.sort(inverse[np.asarray(t)], axis=1)
    x = v[t]
    negative = np.linalg.det(np.stack([x[:, j] - x[:, 0] for j in (1, 2, 3)], axis=2)) < 0
    t[negative, :2] = t[negative, 1::-1]
    labels = np.asarray(labels)
    order = np.lexsort(np.column_stack([labels, t]).T[::-1])
    return v, t[order], labels[order]


def packet(v, t, labels):
    return dict(
        vertices_m=np.asarray(v).tolist(),
        tetrahedra=np.asarray(t).tolist(),
        labels=np.asarray(labels).tolist(),
    )


def canonical_surfaces(bs):
    result = []
    for m in bs:
        v = m.vertices.xyz
        order = np.lexsort(v.T[::-1])
        inverse = np.empty(len(order), int)
        inverse[order] = np.arange(len(order))
        f = inverse[m.faces].copy()
        f = np.array([np.roll(row, -np.argmin(row)) for row in f])
        f = f[np.lexsort(f.T[::-1])]
        result.append(Mesh(Points(v[order], Frame.MRI), f, {"synthetic": True}))
    return result


def surface_packet(bs):
    return [dict(vertices_m=m.vertices.xyz.tolist(), faces=m.faces.tolist()) for m in bs]


def native(surfaces, electrodes, options):
    import gmsh

    actual = {}
    generate = gmsh.model.mesh.generate

    def capture(dim):
        for key, value in options.items():
            gmsh.option.setNumber(key, value)
        for key in [
            "General.NumThreads",
            "Mesh.Algorithm3D",
            "Mesh.RandomSeed",
            "Mesh.RandomFactor",
            "Mesh.RandomFactor3D",
            "Mesh.Reproducible",
            "Mesh.Optimize",
            "Mesh.OptimizeNetgen",
            "Mesh.MeshSizeMax",
            "Mesh.MeshSizeMin",
            "Mesh.MeshOnlyEmpty",
        ]:
            actual[key] = gmsh.option.getNumber(key)
        return generate(dim)

    with patch.object(gmsh.model.mesh, "generate", capture):
        mesh = gmsh_mesh(surfaces, electrodes, 0.025)
    return (*mesh, actual)


def solve(v, t, labels, p, e, quadrature=8, permutation=False):
    import skfem

    import soma.source.fem_reference as fem

    matrices = []
    rhs = []
    original_asm = skfem.asm
    original_lu = fem.splu

    def assembly(*args, **kwargs):
        value = original_asm(*args, **kwargs)
        if getattr(value, "ndim", 0) == 2:
            a = value.tocsr(copy=True)
            a.sort_indices()
            matrices.append(
                dict(
                    shape=list(a.shape),
                    indptr=a.indptr.tolist(),
                    indices=a.indices.tolist(),
                    data=a.data.tolist(),
                )
            )
        return value

    def factor(a):
        lu = original_lu(a, permc_spec="NATURAL") if permutation else original_lu(a)

        class Capture:
            def solve(self, b):
                rhs.append(np.asarray(b).tolist())
                return lu.solve(b)

        return Capture()

    with patch.object(skfem, "asm", assembly), patch.object(fem, "splu", factor):
        g, d = full_subtraction(v, t, labels, p, e, [0.33] * 4, quadrature=quadrature)
    return dict(
        lead=g.tolist(),
        diagnostics=d,
        stiffness=matrices[0],
        rhs_reduced=np.array(rhs).T.tolist(),
        dtype=str(g.dtype),
        sparse_order="NATURAL" if permutation else "COLAMD",
    )


def run(output, create_fixture=False):
    bs = boundaries(None, 1)
    e = sensors(None)
    p = np.array([[0.0, 0.0, 0.0], [0.02, 0.0, 0.0]])
    v, t, labels, quality, actual_options = native(bs, e, {})
    if create_fixture:
        assert not FIXTURE.exists(), "Diagnostic fixture is immutable once captured"
        FIXTURE.write_text(
            json.dumps(
                dict(
                    schema="soma.mesh-grid.diagnostic-fixture/1",
                    synthetic_only=True,
                    provenance=(
                        "Post-outcome diagnostic, not the M30 frozen study "
                        "or a replacement native-meshing gate"
                    ),
                    mesh=packet(v, t, labels),
                    surfaces=surface_packet(bs),
                    sources_m=p.tolist(),
                    sensors_m=e.tolist(),
                ),
                indent=2,
            )
            + "\n"
        )
    fixture = json.loads(FIXTURE.read_text())
    fixed_bs = [
        Mesh(Points(m["vertices_m"], Frame.MRI), np.array(m["faces"]), {"synthetic": True})
        for m in fixture["surfaces"]
    ]
    results = {}
    for name, surfaces, options in [
        ("native", bs, {}),
        ("canonical_input", canonical_surfaces(bs), {}),
        ("shared_input", fixed_bs, {}),
        ("alternate_seed", fixed_bs, {"Mesh.RandomSeed": 30043}),
        ("reproducible_option", fixed_bs, {"Mesh.Reproducible": 1}),
        ("random_factor_zero", fixed_bs, {"Mesh.RandomFactor": 0, "Mesh.RandomFactor3D": 0}),
    ]:
        try:
            if name != "native":
                v, t, labels, quality, actual_options = native(surfaces, e, options)
            canonical = packet(*canonical_mesh(v, t, labels))
            results[name] = dict(
                mesh=packet(v, t, labels),
                mesh_hash=quality["mesh_hash"],
                canonical_mesh_hash=fingerprint(canonical),
                quality=quality,
                surface_hash=fingerprint(surface_packet(surfaces)),
                sources_hash=fingerprint(p.tolist()),
                sensors_hash=fingerprint(e.tolist()),
                options=actual_options,
                **solve(v, t, labels, p, e),
            )
        except Exception as exc:
            results[name] = dict(
                status="FAILED", reason=type(exc).__name__ + ": " + str(exc).splitlines()[0]
            )
    m = fixture["mesh"]
    v, t, labels = np.array(m["vertices_m"]), np.array(m["tetrahedra"]), np.array(m["labels"])
    audit_volume(v, t, labels, fixed_bs)
    native_sources, native_sensors = p.copy(), e.copy()
    p = np.array(fixture["sources_m"], dtype=np.float64)
    e = np.array(fixture["sensors_m"], dtype=np.float64)
    results["shared_mesh"] = solve(v, t, labels, p, e)
    results["shared_mesh_natural_lu"] = solve(v, t, labels, p, e, permutation=True)
    results["shared_mesh_q6"] = solve(v, t, labels, p, e, quadrature=6)
    # Same physical cells, different assembly/reduction/node/gauge ordering.
    order = np.arange(len(v))[::-1]
    inverse = np.empty(len(order), int)
    inverse[order] = np.arange(len(order))
    results["shared_mesh_reordered"] = solve(
        v[order], inverse[t[::-1]][:, [1, 2, 0, 3]], labels[::-1], p, e
    )
    # Probe the process C runtime independently, after all native meshing.
    libc = ctypes.CDLL(None)
    libc.srand.argtypes = [ctypes.c_uint]
    libc.rand.restype = ctypes.c_int
    libc.srand(30042)
    c_random_sequence = [int(libc.rand()) for _ in range(8)]
    data = dict(
        schema="soma.mesh-grid.causal-diagnostic/1",
        environment=dict(
            system=platform.system(),
            machine=platform.machine(),
            python=platform.python_version(),
            packages={
                n: importlib.metadata.version(n) for n in ["gmsh", "numpy", "scipy", "scikit-fem"]
            },
            blas={
                name: {
                    k: v
                    for k, v in module.show_config(mode="dicts")
                    .get("Build Dependencies", {})
                    .get("blas", {})
                    .items()
                    if k in ["name", "version", "openblas configuration", "has ilp64"]
                }
                for name, module in [("numpy", np), ("scipy", scipy)]
            },
            threadpools=[
                {k: v for k, v in item.items() if k != "filepath"} for item in threadpool_info()
            ],
        ),
        fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        original_surface_hash=fingerprint(surface_packet(bs)),
        canonical_surface_hash=fingerprint(surface_packet(canonical_surfaces(bs))),
        sources_m=native_sources.tolist(),
        sensors_m=native_sensors.tolist(),
        shared_sources_m=p.tolist(),
        shared_sensors_m=e.tolist(),
        C_runtime_random_seed=30042,
        C_runtime_random_sequence=c_random_sequence,
        controls=results,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--create-fixture", action="store_true")
    args = parser.parse_args()
    run(args.output, args.create_fixture)
