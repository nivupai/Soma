"""Prospective release policy: validate all native evidence, retain known FAIL."""

import argparse
import hashlib
import json
import math
import os
import re
from numbers import Real
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

from scripts.canonical_mesh_repro import PROTOCOL_SHA256 as CANONICAL_PROTOCOL_SHA256
from scripts.canonical_mesh_repro import load_inputs
from scripts.compare_mesh_grids import compare as frozen_compare
from scripts.mesh_grid_diagnostic import canonical_mesh, fingerprint, packet
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.source.bem_discrepancy import homogeneous_series
from soma.source.mesh_replication import audit_volume, candidate_grid, nearest_distances
from soma.source.noise import average_projector

POLICY_PATH = Path("configs/release-policy-v030-v1.json")
POLICY_SHA256 = "b50a7f656943bc620b066ea7285fd2c572b8c4f1722ad8acbd38de8fd8eeb2aa"
CONTROLS = {
    "native",
    "canonical_input",
    "shared_input",
    "alternate_seed",
    "reproducible_option",
    "random_factor_zero",
    "shared_mesh",
    "shared_mesh_natural_lu",
    "shared_mesh_q6",
    "shared_mesh_reordered",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    require(path.is_file(), "Missing required native diagnostic report or policy file")
    require(path.stat().st_size <= 8 * 1024**2, "Oversized native diagnostic report")

    def invalid(_):
        raise ValueError("Nonfinite JSON native diagnostic value")

    value = json.loads(path.read_text(), parse_constant=invalid)
    require(isinstance(value, dict), "Native report must be a JSON object")
    return value


def array(value, shape, integer=False):
    a = np.asarray(value)
    require(a.dtype.kind in ("iu" if integer else "iuf"), "Invalid native numeric type")
    require(
        a.ndim == len(shape)
        and all(s is None or s == n for s, n in zip(shape, a.shape, strict=True)),
        "Invalid native array dimensions",
    )
    require(np.isfinite(a).all(), "Nonfinite native array")
    return a


def scalar(value, low, high, *, strict_low=False, strict_high=False):
    require(
        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value),
        "Invalid native scalar",
    )
    require(
        (low < value if strict_low else low <= value)
        and (value < high if strict_high else value <= high),
        "Native scalar outside physical bounds",
    )
    return float(value)


def identity(environment):
    require(isinstance(environment, dict), "Invalid native environment")
    require(
        all(isinstance(environment.get(k), str) for k in ["system", "machine", "python"]),
        "Incomplete native environment",
    )
    require(
        re.fullmatch(r"3\.(11|12)\.\d+", environment["python"]) is not None,
        "Invalid native Python version",
    )
    return f"{environment['system']}-{environment['machine']}-" + ".".join(
        environment["python"].split(".")[:2]
    )


def validated_mesh(mesh, fixture):
    require(set(mesh) == {"vertices_m", "tetrahedra", "labels"}, "Incomplete native mesh packet")
    v = array(mesh["vertices_m"], (None, 3))
    t = array(mesh["tetrahedra"], (None, 4), True)
    labels = array(mesh["labels"], (len(t),), True)
    require(4 <= len(v) <= 18000 and 1 <= len(t) <= 100000, "Native mesh resource bounds")
    surfaces = []
    for surface in fixture["surfaces"]:
        expected = np.array(surface["vertices_m"])
        dist = np.linalg.norm(expected[:, None] - v[None], axis=2)
        indices = dist.argmin(axis=1)
        require(
            float(dist[np.arange(len(indices)), indices].max()) <= 1e-15
            and len(np.unique(indices)) == len(indices),
            "Native physical interface coordinate drift",
        )
        surfaces.append(
            Mesh(Points(v[indices], Frame.MRI), np.array(surface["faces"]), dict(synthetic=True))
        )
    return audit_volume(v, t, labels, surfaces)


def control(name, c, d, fixture):
    require(
        isinstance(c, dict) and c.get("status") not in ["FAILED", "failed"],
        "Unreported native control failure",
    )
    shared = name.startswith("shared_mesh")
    expected = {"lead", "diagnostics", "stiffness", "rhs_reduced", "dtype", "sparse_order"}
    if not shared:
        expected |= {
            "mesh",
            "mesh_hash",
            "canonical_mesh_hash",
            "quality",
            "surface_hash",
            "sources_hash",
            "sensors_hash",
            "options",
        }
    require(set(c) == expected, "Incomplete or unsupported native control report")
    if shared:
        m = fixture["mesh"]
        if name == "shared_mesh_reordered":
            v = np.array(m["vertices_m"])
            t = np.array(m["tetrahedra"])
            labels = np.array(m["labels"])
            order = np.arange(len(v))[::-1]
            inverse = np.argsort(order)
            m = packet(v[order], inverse[t[::-1]][:, [1, 2, 0, 3]], labels[::-1])
    else:
        m = c["mesh"]
    q = validated_mesh(m, fixture)
    n = q["nodes"]
    diag = c["diagnostics"]
    require(isinstance(diag, dict), "Invalid native solver diagnostic")
    for key in ["nodes", "elements", "tissue_counts", "mesh_hash"]:
        require(diag[key] == q[key], "Native mesh identity/labels mismatch")
    for key in ["min_volume_m3", "min_mean_ratio", "max_mean_ratio"]:
        scalar(diag[key], 0, 1, strict_low=True)
        require(
            np.isclose(diag[key], q[key], rtol=1e-10, atol=1e-15), "Native mesh quality mismatch"
        )
    require(
        diag["units"] == "V/(A*m)"
        and diag["frame"] == "MRI_RAS_m"
        and diag["source_order"] == "source-major XYZ"
        and diag["reference"] == "sensor average"
        and diag["solver_version"] == "12.0.2"
        and diag["independent_of_OpenMEEG"] is True
        and diag["quadrature"] == (6 if name == "shared_mesh_q6" else 8),
        "Invalid native solver physical contract",
    )
    scalar(diag["relative_residual"], 0, 1e-10, strict_high=True)
    scalar(diag["preprojection_current_imbalance"], 0, 1e-3)
    scalar(diag["seconds"], 0, 1e8)
    require(
        c["dtype"] == "float64"
        and c["sparse_order"] == ("NATURAL" if name == "shared_mesh_natural_lu" else "COLAMD"),
        "Native precision or solver ordering changed",
    )
    lead = array(c["lead"], (32, 6))
    require(np.max(np.abs(lead.mean(axis=0))) <= 1e-10, "Native average reference violated")
    matrix = c["stiffness"]
    require(
        set(matrix) == {"shape", "indptr", "indices", "data"}, "Incomplete native stiffness matrix"
    )
    require(
        np.array_equal(array(matrix["shape"], (2,), True), [n, n]), "Invalid native stiffness shape"
    )
    indptr = array(matrix["indptr"], (n + 1,), True)
    indices = array(matrix["indices"], (None,), True)
    data = array(matrix["data"], (len(indices),))
    require(
        indptr[0] == 0
        and indptr[-1] == len(data)
        and np.all(np.diff(indptr) >= 0)
        and np.all((indices >= 0) & (indices < n)),
        "Invalid native CSR structure",
    )
    a = csr_matrix((data, indices, indptr), shape=(n, n))
    require(np.all(a.diagonal() > 0), "Invalid native stiffness diagonal")
    difference = (a - a.T).data
    require(
        not len(difference) or np.max(np.abs(difference)) <= 1e-10 * np.max(np.abs(data)),
        "Invalid native stiffness symmetry",
    )
    array(c["rhs_reduced"], (n - 1, 6))
    if not shared:
        require(
            c["mesh_hash"] == q["mesh_hash"]
            and c["canonical_mesh_hash"]
            == fingerprint(
                packet(
                    *canonical_mesh(
                        np.array(m["vertices_m"]), np.array(m["tetrahedra"]), np.array(m["labels"])
                    )
                )
            ),
            "Corrupt native mesh fingerprint",
        )
        require(
            c["sources_hash"] == fingerprint(d["sources_m"])
            and c["sensors_hash"] == fingerprint(d["sensors_m"]),
            "Native source/sensor identity mismatch",
        )
        quality = c["quality"]
        require(
            set(quality)
            == set(q)
            | {
                "mesher",
                "mesher_version",
                "mesh_seconds",
                "max_size_m",
                "native_minSICN",
                "boundary_policy",
            },
            "Incomplete native mesh quality report",
        )
        require(
            quality["boundary_policy"]
            == "MeshOnlyEmpty; imported discrete facets retained; no Soma extrusion",
            "Native boundary policy changed",
        )
        for key in ["min_volume_m3", "min_mean_ratio", "max_mean_ratio"]:
            scalar(quality[key], 0, 1, strict_low=True)
            require(
                np.isclose(quality[key], q[key], rtol=1e-10, atol=1e-15),
                "Native quality value mismatch",
            )
        require(
            quality["interface_connectivity_verified"] is True
            and quality["mesher"] == "Gmsh"
            and quality["mesher_version"] == "4.15.2"
            and quality["max_size_m"] == 0.025,
            "Native mesh method or interface mismatch",
        )
        for key in ["nodes", "elements", "tissue_counts", "mesh_hash"]:
            require(quality[key] == q[key], "Native quality/mesh inconsistency")
        require(
            np.allclose(
                array(quality["tissue_volumes_m3"], (4,)),
                q["tissue_volumes_m3"],
                rtol=1e-10,
                atol=1e-14,
            ),
            "Native tissue volume inconsistency",
        )
        scalar(quality["boundary_coordinate_max_m"], 0, 1e-12)
        scalar(quality["native_minSICN"], 0, 1, strict_low=True)
        scalar(quality["mesh_seconds"], 0, 1e8)
        require(
            isinstance(c["options"], dict)
            and all(
                isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(v)
                for v in c["options"].values()
            ),
            "Invalid native numerical options",
        )
        expected_options = {
            "General.NumThreads": 1,
            "Mesh.MeshOnlyEmpty": 1,
            "Mesh.MeshSizeMax": 0.025,
            "Mesh.MeshSizeMin": 0.001,
            "Mesh.Algorithm3D": 1,
            "Mesh.Optimize": 1,
            "Mesh.OptimizeNetgen": 0,
            "Mesh.RandomSeed": 30043 if name == "alternate_seed" else 30042,
            "Mesh.Reproducible": 1 if name == "reproducible_option" else 0,
            "Mesh.RandomFactor": 0 if name == "random_factor_zero" else 1e-9,
            "Mesh.RandomFactor3D": 0 if name == "random_factor_zero" else 1e-12,
        }
        require(c["options"] == expected_options, "Native numerical options changed")
    return q


def validate_report(report, detail, signature, fixture, expected_quality):
    require(
        set(report) == set(signature["primary_keys"]),
        "Incomplete or unsupported native primary report",
    )
    required_detail = {
        "schema",
        "environment",
        "fixture_sha256",
        "original_surface_hash",
        "canonical_surface_hash",
        "sources_m",
        "sensors_m",
        "shared_sources_m",
        "shared_sensors_m",
        "C_runtime_random_seed",
        "C_runtime_random_sequence",
        "controls",
    }
    require(set(detail) == required_detail, "Incomplete or unsupported native companion report")
    for name in ["original_surface_hash", "canonical_surface_hash"]:
        require(
            isinstance(detail[name], str) and re.fullmatch(r"[0-9a-f]{64}", detail[name]),
            "Invalid native provenance hash",
        )
    require(detail["C_runtime_random_seed"] == 30042, "Native random probe seed changed")
    sequence = array(detail["C_runtime_random_sequence"], (8,), True)
    require(np.all((sequence >= 0) & (sequence <= 2**31 - 1)), "Invalid native random probe")
    require(
        set(detail["environment"])
        == {"system", "machine", "python", "packages", "blas", "threadpools"},
        "Incomplete native numerical environment",
    )
    key = identity(report["environment"])
    require(
        set(report["environment"]) == {"system", "machine", "python"},
        "Invalid native environment fields",
    )
    require(
        report["schema"] == "soma.mesh-grid.repro/1"
        and report["protocol"] == signature["native_protocol"]
        and report["scope"] == signature["scope"],
        "Native schema/protocol/scope drift",
    )
    lead = array(report["lead"], (32, 6))
    scalar(report["relative"], 0, 0.15, strict_low=True, strict_high=True)
    scalar(report["min_mean_ratio"], 0.01, 1)
    scalar(report["boundary_coordinate_max_m"], 0, 1e-12)
    volumes = array(report["tissue_volumes_m3"], (4,))
    require(
        np.all(volumes > 0)
        and np.allclose(volumes, expected_quality["tissue_volumes_m3"], rtol=1e-10, atol=1e-14),
        "Invalid native tissue volumes",
    )
    nearest = array(report["nearest_mm"], (3,))
    expected = [
        float(nearest_distances(candidate_grid(s).xyz, np.array([[0.012, 0.023, 0.034]]))[0])
        for s in [30, 20, 15]
    ]
    require(
        np.allclose(nearest, expected, rtol=1e-12, atol=1e-12), "Invalid native nearest-grid report"
    )
    require(
        detail["schema"] == "soma.mesh-grid.causal-diagnostic/1"
        and identity(detail["environment"]) == key
        and detail["environment"]["python"] == report["environment"]["python"],
        "Native companion provenance mismatch",
    )
    require(
        detail["fixture_sha256"]
        == hashlib.sha256(Path("configs/mesh-grid-control-v30.json").read_bytes()).hexdigest(),
        "Native diagnostic fixture mismatch",
    )
    require(
        detail["environment"]["packages"]["gmsh"] == "4.15.2"
        and detail["environment"]["packages"]["scikit-fem"] == "12.0.2",
        "Native numerical implementation changed",
    )
    p = array(detail["sources_m"], (2, 3))
    e = array(detail["sensors_m"], (32, 3))
    require(
        np.array_equal(p, fixture["sources_m"])
        and np.max(np.abs(e - fixture["sensors_m"])) <= 1e-15,
        "Native source/sensor drift",
    )
    if "shared_sources_m" in detail:
        require(
            np.array_equal(array(detail["shared_sources_m"], (2, 3)), fixture["sources_m"]),
            "Shared source drift",
        )
    if "shared_sensors_m" in detail:
        require(
            np.array_equal(array(detail["shared_sensors_m"], (32, 3)), fixture["sensors_m"]),
            "Shared sensor drift",
        )
    require(
        isinstance(detail["controls"], dict) and set(detail["controls"]) == CONTROLS,
        "Missing or unsupported native control",
    )
    for name, c in detail["controls"].items():
        control(name, c, detail, fixture)
    native = detail["controls"]["native"]
    require(np.array_equal(lead, native["lead"]), "Native primary/companion fields differ")
    require(
        np.isclose(
            report["min_mean_ratio"], native["quality"]["min_mean_ratio"], rtol=1e-10, atol=1e-12
        ),
        "Native primary quality mismatch",
    )
    exact = average_projector(32) @ homogeneous_series(p, e)
    relative = float(np.linalg.norm(lead - exact) / np.linalg.norm(exact))
    require(
        np.isclose(report["relative"], relative, rtol=1e-10, atol=1e-12),
        "Native reference accuracy is inconsistent with fields",
    )
    return key


def report(root, policy_path=POLICY_PATH):
    require(
        hashlib.sha256(policy_path.read_bytes()).hexdigest() == POLICY_SHA256,
        "Release policy integrity failure",
    )
    policy = read_json(policy_path)
    require(
        policy["mandatory_canonical_protocol_sha256"] == CANONICAL_PROTOCOL_SHA256,
        "Canonical mandatory policy identity mismatch",
    )
    require(
        hashlib.sha256(Path(policy["original_native_comparator"]).read_bytes()).hexdigest()
        == policy["original_native_comparator_sha256"],
        "Frozen native comparator changed",
    )
    signature_path = Path(policy["native_signature_path"])
    require(
        hashlib.sha256(signature_path.read_bytes()).hexdigest()
        == policy["native_signature_sha256"],
        "Native signature integrity failure",
    )
    signature = read_json(signature_path)
    for historical in signature["historical_reports"].values():
        require(
            hashlib.sha256(Path(historical["path"]).read_bytes()).hexdigest()
            == historical["sha256"],
            "Historical native evidence changed",
        )
    _, _, quality, _ = load_inputs()
    fixture = read_json(Path("configs/mesh-grid-control-v30.json"))
    paths = sorted(Path(root).glob("*/mesh-grid-synthetic.json"))
    require(len(paths) == 4, "Missing or extra native reports: four required")
    reports = {}
    # Validate EVERY report and companion before executing a comparator that may short-circuit.
    for path in paths:
        value = read_json(path)
        detail = read_json(path.parent / "mesh-grid-diagnostic.json")
        key = validate_report(value, detail, signature, fixture, quality)
        require(key not in reports, "Duplicate native environment")
        reports[key] = value
    require(
        set(reports) == set(signature["historical_reports"]),
        "Incomplete native environment coverage",
    )
    try:
        frozen_compare(root)
    except ValueError as exc:
        if str(exc) != "Cross-platform field disagreement":
            raise
    else:
        raise ValueError("Native diagnostic unexpectedly passed; release-policy review required")
    pairs = []
    for expected in signature["pairs"]:
        baseline = np.array(reports[expected["reference"]]["lead"])
        actual = np.array(reports[expected["actual"]]["lead"])
        delta = actual - baseline
        failed = np.argwhere(np.abs(delta) > 0.01 + 0.02 * np.abs(baseline)).tolist()
        require(
            failed == expected["failed_sensor_columns"],
            "Native failure signature changed; review required",
        )
        require(
            np.allclose(
                delta,
                expected["signed_difference_V_per_Am"],
                rtol=signature["discrepancy_replay_rtol"],
                atol=signature["discrepancy_replay_atol_V_per_Am"],
            ),
            "Uncharacterized native discrepancy vector; review required",
        )
        pairs.append(
            dict(
                reference=expected["reference"],
                actual=expected["actual"],
                failed_sensor_columns=failed,
                failed_entries=len(failed),
                aggregate_relative=float(np.linalg.norm(delta) / np.linalg.norm(baseline)),
            )
        )
    require(any(p["failed_entries"] for p in pairs), "Native numerical failure disappeared")
    return dict(
        schema="soma.native-mesh.release-diagnostic/1",
        release_policy=policy["id"],
        release_policy_sha256=POLICY_SHA256,
        scientific_status="FAIL",
        original_M30_gate="FAIL_PRESERVED",
        all_passed=False,
        native_portability_established=False,
        known_numerical_disagreement=True,
        reports_validated=4,
        companions_validated=4,
        rtol=0.02,
        atol_V_per_Am=0.01,
        classification_only_rtol=signature["discrepancy_replay_rtol"],
        classification_only_atol_V_per_Am=signature["discrepancy_replay_atol_V_per_Am"],
        release_disposition="NONBLOCKING_CHARACTERIZED_SCIENTIFIC_FAILURE",
        release_policy_satisfied=True,
        pairs=pairs,
        merge_authorized=False,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--github-summary", action="store_true")
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "Native Gmsh scientific diagnostic: FAIL. Original M30 gate remains FAILED. "
        "Only the fully validated, previously characterized discrepancy is nonblocking "
        "under prospective release policy v1. Native portability is NOT established. "
        "Canonical-mesh and all other release checks remain mandatory."
    )
    try:
        if a.github_summary:
            require(
                bool(os.environ.get("GITHUB_STEP_SUMMARY")), "Missing GitHub summary destination"
            )
        result = report(a.root)
        if a.github_summary:
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
                stream.write("## Native Gmsh scientific diagnostic: FAIL\n\n" + text + "\n")
    except Exception as exc:
        a.output.write_text(
            json.dumps(
                dict(
                    schema="soma.native-mesh.release-diagnostic/1",
                    scientific_status="INVALID_OR_UNEXPECTED",
                    release_disposition="BLOCK_RELEASE",
                    release_policy_satisfied=False,
                    error_type=type(exc).__name__,
                    reason=str(exc),
                ),
                indent=2,
            )
            + "\n"
        )
        raise
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(text)


if __name__ == "__main__":
    main()
