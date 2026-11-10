"""Known controlled histories and explicit numerical/identity failures."""

import copy
import hashlib
import json

import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.protocol.binding import Snapshot, example_protocol, example_snapshot
from soma.protocol.examples import method_amendment
from soma.protocol.history import historical_evidence
from soma.protocol.model import ProtocolError, amend, seal
from soma.protocol.replay import (
    Execution,
    append_history,
    compare,
    history,
    plan,
    read_execution,
    run,
    write_execution,
)
from soma.results.contracts import canonical
from soma.workflow.privacy import redact_export


def rehash(value):
    d = copy.deepcopy(value)
    d["record_sha256"] = hashlib.sha256(
        canonical({k: v for k, v in d.items() if k != "record_sha256"})
    ).hexdigest()
    return Execution.from_dict(d)


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    root = tmp_path_factory.mktemp("protocol-records")
    result = {}
    for f in ["eeg", "mri", "fmri", "source"]:
        p = example_protocol(f)
        s = seal(p)
        snap = example_snapshot(p, count=2 if f == "eeg" else 1)
        a = run(s, snap, root / f, sequence=1)
        b = run(s, snap, root / (f + "-recomputed"), sequence=2, reference=a)
        result[f] = (p, s, snap, a, b, root / f)
    return result


@pytest.mark.parametrize("family", ["eeg", "mri", "fmri", "source"])
def test_exact_three_distinct_output_identity_observations(recorded, family):
    _, _, _, a, b, _ = recorded[family]
    r = compare(a, b)
    assert r["authorized"] and r["numerically_identical"] and r["numerically_equivalent"]
    assert r["artifact_byte_identical"] and not r["confirmatory_replication_authorized"]
    assert b.record()["replay_assessment"]["authorized"]


@pytest.mark.parametrize("mode", ["CONTROLLED", "EXPLORATORY"])
def test_reference_required_before_computation(mode, tmp_path):
    p = example_protocol("eeg")
    s = example_snapshot(p)
    with pytest.raises(ProtocolError):
        plan(seal(p), s, mode=mode, cache_root=tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


def test_added_independent_units_and_preserved_denominators(recorded):
    p, s, _, a, _, root = recorded["eeg"]
    expanded = example_snapshot(p, count=3, identity="expanded")
    b = run(s, expanded, root, sequence=3, mode="CONTROLLED", reference=a)
    r = compare(a, b, mode="CONTROLLED")
    assert r["authorized"] and r["status"] == "CONTROLLED_DATA_CHANGE"
    assert r["unit_counts"] == {"left": 2, "right": 3, "shared": 2, "added": 1, "removed": 0}
    assert not r["numerical_equivalence_applicable"]
    assert any(x["category"] == "DATA_DRIFT" for x in r["drift"])
    assert all(m["qc"]["all_complete"] for m in b.record()["members"])
    smaller = example_snapshot(p, count=1, identity="selected")
    with pytest.raises(ProtocolError):
        run(s, smaller, root, sequence=4, mode="CONTROLLED", reference=a)


@pytest.mark.parametrize("family", ["eeg", "mri", "fmri", "source"])
def test_scientific_method_revisions_are_exploratory(recorded, family):
    p, _, snap, a, _, root = recorded[family]
    new = seal(method_amendment(p, family))
    with pytest.raises(ProtocolError):
        run(new, snap, root, sequence=5, mode="CONTROLLED", reference=a)
    revised = run(new, snap, root, sequence=5, mode="EXPLORATORY", reference=a)
    result = compare(a, revised, mode="EXPLORATORY")
    assert result["authorized"] and result["status"] == "EXPLORATORY_DESCRIPTIVE"
    assert result["numerically_equivalent"] is None
    assert not compare(a, revised, mode="CONTROLLED")["authorized"]
    assert any(x["category"] == "PROTOCOL_DRIFT" for x in result["drift"])
    assert not result["confirmatory_replication_authorized"]


def test_source_conductivity_change_is_visible_and_unsupported(recorded):
    p, _, snap, a, _, root = recorded["source"]
    d = p.document()
    d["version"] = "2.0.0"
    d["scientific"]["source_conductivity"] = {"S_m": [0.3, 0.006, 0.3]}
    new = amend(p, d, reason="physical model proposal", authorization_reference="local")
    b = run(seal(new), snap, root, sequence=6, mode="EXPLORATORY", reference=a)
    assert b.record()["status"] == "PARTIAL"
    assert any(
        d["category"] == "UNSUPPORTED_FORWARD_SPECIFICATION" for d in b.record()["deviations"]
    )
    assessment = compare(a, b, mode="EXPLORATORY")
    assert assessment["status"] == "INDETERMINATE"
    assert "DATA_DRIFT" not in {d["category"] for d in assessment["drift"]}


def test_missing_unit_never_disappears_as_favorable_subset(recorded):
    _, s, snap, a, _, root = recorded["eeg"]
    d = snap.document()
    d["id"] = "missing-snapshot"
    d["members"][1].update(available=False, reason="INPUT_MISSING")
    b = run(s, Snapshot.from_dict(d), root, sequence=7, mode="CONTROLLED", reference=a)
    assert len(b.record()["members"]) == 2 and b.record()["status"] == "PARTIAL"
    r = compare(a, b, mode="CONTROLLED")
    assert r["status"] == "INDETERMINATE" and not r["authorized"]
    assert any(x["category"] == "MISSING_OR_UNVERIFIABLE_EVIDENCE" for x in r["drift"])


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-software",
        "invalid-version",
        "invalid-build",
        "incomplete-members",
        "changed-estimand",
        "invalid-time",
        "corrupt-hash",
    ],
)
def test_execution_record_integrity(recorded, mutation):
    a = recorded["eeg"][3].record()
    if mutation == "missing-software":
        del a["environment"]["libraries"]
    elif mutation == "invalid-version":
        a["environment"]["libraries"]["numpy"] = "not-a-version"
    elif mutation == "invalid-build":
        a["environment"]["numerical_build_metadata_sha256"]["numpy"] = "not-a-hash"
    elif mutation == "incomplete-members":
        a["members"] = a["members"][:1]
    elif mutation == "changed-estimand":
        a["protocol"]["protocol"]["scientific"]["estimand"] = "tampered"
    elif mutation == "invalid-time":
        a["finished_at"] = "2000-01-01"
    else:
        a["record_sha256"] = "0" * 64
    with pytest.raises(ProtocolError):
        if mutation == "corrupt-hash":
            Execution.from_dict(a)
        else:
            rehash(a)


def test_environment_drift_not_cache_authorization(recorded):
    a = recorded["source"][3]
    d = a.record()
    d["execution_id"] = "different"
    d["sequence"] = 2
    d["environment"]["kernel_build"] += " synthetic test variation"
    b = rehash(d)
    assert not compare(a, b, mode="EXACT")["authorized"]
    r = compare(a, b, mode="CONTROLLED")
    assert r["authorized"] and r["numerically_equivalent"] and not r["cache_interchangeability"]
    assert any(x["category"] == "EXECUTION_ENVIRONMENT_DRIFT" for x in r["drift"])
    d = b.record()
    d["implementation_fingerprint"] = "0" * 64
    c = rehash(d)
    assert not compare(a, c, mode="CONTROLLED")["authorized"]


def test_frozen_tolerance_failure_and_no_posthoc_widening(recorded):
    a = recorded["source"][3]
    d = a.record()
    d["execution_id"] = "perturbed"
    d["sequence"] = 2
    d["members"][0]["numerical_summary"][0] += 0.01
    b = rehash(d)
    r = compare(a, b)
    assert not r["authorized"] and r["numerically_equivalent"] is False
    assert (
        r["numerical_comparisons"][0]["atol"]
        == a.record()["protocol"]["protocol"]["tolerances"]["atol"]
    )
    assert any(x["category"] == "NUMERICAL_DRIFT" for x in r["drift"])


def test_history_explicit_sequences_and_no_overwrite(recorded, tmp_path):
    _, _, _, a, b, _ = recorded["source"]
    first = append_history(a, tmp_path / "history")
    second = append_history(b, tmp_path / "history")
    assert [x["sequence"] for x in history([second, first])["executions"]] == [1, 2]
    with pytest.raises(ProtocolError):
        append_history(b, tmp_path / "history")
    with pytest.raises(ProtocolError):
        history([first, first])
    before = first.read_bytes()
    with pytest.raises(ProtocolError):
        write_execution(a, first.parent)
    assert first.read_bytes() == before
    artifact = json.loads(first.read_text())
    artifact["payload"]["values"]["sequence"] = 99
    first.write_text(json.dumps(artifact))
    with pytest.raises(ValueError):
        read_execution(first)


def test_historical_metadata_is_not_fabricated_or_modified(tmp_path):
    (tmp_path / "configs").mkdir()
    p = tmp_path / "configs/freeze.json"
    p.write_text('{"frozen_at_utc":"recorded-original-claim","files_sha256":{}}')
    before = p.read_bytes()
    evidence = historical_evidence(tmp_path, "configs/freeze.json")
    assert evidence["status"] == "INDETERMINATE" and not evidence["historical_source_modified"]
    assert evidence["recorded_declarations"]["frozen_at_utc"] == "recorded-original-claim"
    assert p.read_bytes() == before
    p.write_text('{"files_sha256":{"../private.json":"hash"}}')
    with pytest.raises(ProtocolError):
        historical_evidence(tmp_path, "configs/freeze.json")


def test_private_export_retains_restrictions_and_no_human_claim(recorded):
    value = recorded["eeg"][3].record()
    value["environment"]["private_path"] = "/private/participant"
    value["participant_name"] = "private"
    clean = redact_export(value)
    assert "/private/participant" not in str(clean) and "participant_name" not in clean
    assert clean["snapshot"]["restrictions"] and clean["interpretation"] == "DESCRIPTIVE_ONLY"


def test_cli_uses_actual_seals_and_records(recorded, tmp_path):
    p, s, snap, a, b, _ = recorded["source"]
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(p.document()))
    sealed = tmp_path / "sealed.json"
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(snap.document()))
    runner = CliRunner()
    for command, args in [
        ("validate", [str(protocol)]),
        ("seal", [str(protocol), str(sealed)]),
        ("compare", [str(sealed), str(sealed)]),
    ]:
        response = runner.invoke(app, ["protocol", command, *args])
        assert response.exit_code == 0, response.output
    left = write_execution(a, tmp_path / "left")
    right = write_execution(b, tmp_path / "right")
    for command in ["compare", "drift"]:
        response = runner.invoke(app, ["replay", command, str(left), str(right)])
        assert response.exit_code == 0, response.output
    response = runner.invoke(
        app, ["replay", "plan", str(sealed), str(snapshot), "--cache-root", str(tmp_path / "empty")]
    )
    assert response.exit_code == 0 and not (tmp_path / "empty").exists()


def test_execution_reader_rejects_array_bearing_container_without_materialization(
    recorded, tmp_path
):
    from unittest.mock import patch

    import numpy as np

    from soma.results.contracts import create_result
    from soma.results.io import inspect_result, save_result

    original = write_execution(recorded["source"][3], tmp_path / "original")
    envelope = inspect_result(original)["envelope"]
    replacement = create_result(
        "experiment.manifest",
        envelope["payload"]["domain"],
        arrays={"unexpected": np.array([1.0])},
        values=envelope["payload"]["values"],
        provenance=envelope["provenance"],
        interpretation_state="DESCRIPTIVE_ONLY",
        method=envelope["method"],
        parameters={},
        units={},
    )
    path = save_result(replacement, {"unexpected": np.array([1.0])}, tmp_path / "array-record")
    with patch("numpy.load", side_effect=AssertionError("Unexpected array loading")):
        with pytest.raises(ProtocolError, match="Not a protocol execution artifact"):
            read_execution(path)
