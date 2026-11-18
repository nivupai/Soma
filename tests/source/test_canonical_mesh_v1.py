"""Canonical control identity and the unchanged per-entry acceptance criterion."""

import copy
import json

import numpy as np
import pytest

from scripts import canonical_mesh_repro as canonical
from scripts.compare_canonical_mesh import compare


@pytest.fixture(scope="module")
def result():
    return canonical.run()


def four_reports(tmp_path, result):
    # Unit-test inputs only; never exported as actual runner evidence.
    for i, (system, machine, version) in enumerate(
        [
            ("Linux", "x86_64", "3.11.0"),
            ("Linux", "x86_64", "3.12.0"),
            ("Darwin", "arm64", "3.11.0"),
            ("Darwin", "arm64", "3.12.0"),
        ]
    ):
        value = copy.deepcopy(result)
        env = dict(system=system, machine=machine, python=version)
        value["environment"] = env
        value["strict_field_report"]["environment"] = env
        folder = tmp_path / str(i)
        folder.mkdir()
        (folder / "canonical-mesh-v1.json").write_text(json.dumps(value))
    return tmp_path


def test_serialized_mesh_corruption_is_rejected(tmp_path):
    p = tmp_path / "fixture.json"
    p.write_bytes(canonical.FIXTURE_PATH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="fixture integrity"):
        canonical.load_inputs(fixture_path=p)


def test_protocol_change_requires_new_version(tmp_path):
    p = tmp_path / "protocol.json"
    v = json.loads(canonical.PROTOCOL_PATH.read_text())
    v["field_rtol"] = 0.03
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="protocol integrity"):
        canonical.load_inputs(protocol_path=p)


def test_canonical_calculation_never_invokes_native_meshing(monkeypatch):
    import soma.source.mesh_replication as mesher

    monkeypatch.setattr(mesher, "gmsh_mesh", lambda *_: pytest.fail("Native mesher invoked"))
    r = canonical.run()
    assert not r["native_meshing_invoked"]
    assert np.array(r["strict_field_report"]["lead"]).shape == (32, 6)
    assert r["solver_diagnostics"]["relative_residual"] < 1e-10


def test_separate_experiment_uses_original_strict_comparator(tmp_path, result):
    r = compare(four_reports(tmp_path, result))
    assert r["all_passed"] and r["rtol"] == 0.02 and r["atol_V_per_Am"] == 0.01
    assert r["native_mesh_reproducibility"] == "NOT_ESTABLISHED_SEPARATE_FAILED_NATIVE_GATE"
    assert r["release_gate_decision"] == "NOT_AUTHORIZED"


def test_exact_input_identity_cannot_be_spoofed(tmp_path, result):
    root = four_reports(tmp_path, result)
    p = root / "1/canonical-mesh-v1.json"
    v = json.loads(p.read_text())
    v["physical_fingerprints"]["labels"] = "0" * 64
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        compare(root)


def test_four_independent_environments_required(tmp_path, result):
    root = four_reports(tmp_path, result)
    p = root / "1/canonical-mesh-v1.json"
    v = json.loads(p.read_text())
    v["environment"]["python"] = "3.11.0"
    v["strict_field_report"]["environment"] = v["environment"]
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="coverage"):
        compare(root)


def test_wrong_physical_units_rejected(tmp_path, result):
    root = four_reports(tmp_path, result)
    p = root / "1/canonical-mesh-v1.json"
    v = json.loads(p.read_text())
    v["solver_diagnostics"]["units"] = "uV/(A*m)"
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="physical contract"):
        compare(root)


def test_small_aggregate_delta_does_not_replace_entrywise_gate(tmp_path, result):
    root = four_reports(tmp_path, result)
    for p in root.glob("*/canonical-mesh-v1.json"):
        v = json.loads(p.read_text())
        a = np.full((32, 6), 100.0)
        a[0, 0] = 0.0
        if p.parent.name == "1":
            a[0, 0] = 0.0100001
        v["strict_field_report"]["lead"] = a.tolist()
        p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="Cross-platform field disagreement"):
        compare(root)
