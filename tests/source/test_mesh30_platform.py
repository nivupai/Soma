"""Diagnostic identity and elementwise checks preserve the frozen M30 gate."""

import numpy as np

from scripts.diagnose_mesh_grid_entries import entries
from scripts.mesh_grid_diagnostic import canonical_mesh, fingerprint, packet


def test_mesh_fingerprint_removes_numbering_but_detects_physical_changes():
    v = np.array([[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [0.0, 0.01, 0.0], [0.0, 0.0, 0.01]])
    t = np.array([[0, 1, 2, 3]])
    labels = np.array([0])
    first = fingerprint(packet(*canonical_mesh(v, t, labels)))
    order = np.array([2, 0, 3, 1])
    inverse = np.argsort(order)
    assert (
        fingerprint(packet(*canonical_mesh(v[order], inverse[t][:, [1, 2, 0, 3]], labels))) == first
    )
    changed = v.copy()
    changed[1, 0] += 1e-12
    assert fingerprint(packet(*canonical_mesh(changed, t, labels))) != first
    assert fingerprint(packet(*canonical_mesh(v, t, labels + 1))) != first


def test_small_aggregate_error_does_not_override_elementwise_failure():
    reference = np.full((32, 6), 100.0)
    reference[7, 4] = 0.0
    actual = reference.copy()
    actual[7, 4] = 0.0100001
    rows = entries(actual, reference)
    failed = [r for r in rows if r["failed"]]
    assert len(failed) == 1
    assert failed[0]["sensor_index"] == 7 and failed[0]["source_index"] == 1
    assert failed[0]["orientation"] == "Y" and failed[0]["relative_difference"] is None
    assert failed[0]["applied_tolerance_V_per_Am"] == 0.01
    assert np.linalg.norm(actual - reference) / np.linalg.norm(reference) < 1e-5
