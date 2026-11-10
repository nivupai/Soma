"""Session relationships and fail-closed frozen-protocol gates, without human inference."""

import copy
import hashlib
import json
from unittest.mock import patch

import pytest

from soma.human.adapters import Selection, identity
from soma.human.evidence import seal_bundle
from soma.human.model import Identity
from soma.human.permissions import evidence
from soma.human.readiness import (
    Gate,
    aggregate,
    execution_readiness,
    read_readiness,
    session_audit,
    validate_readiness,
    write_readiness,
)
from soma.human.workflow import freeze_cohort, template
from soma.protocol.model import Protocol
from tests.readiness.test_evidence import CONTENT, entry

KEY = bytes(range(32))


def person(session="a", run=None, subject="fictional", dataset="fixture"):
    return identity(
        dataset,
        "1",
        subject,
        KEY,
        modality="EEG",
        task="motor",
        session=session,
        run=run,
        hashes=[hashlib.sha256(b"fixture").hexdigest()],
        acquisition={"task_definition": "fixed-fixture"},
        temporal={"fs_hz": 160},
        spatial={"frame": "fictional-common"},
    )


def test_two_sessions_keep_one_sampling_unit_and_no_reliability_claim():
    r = session_audit([person("a"), person("b")])
    assert r["relationship"] == "REPEATED_SESSION" and r["independent_participants"] == 1
    assert r["status"] == "READY"
    assert not r["chronology_verified"] and not r["longitudinal_reliability_established"]
    assert not r["common_anatomical_space_established"]


@pytest.mark.parametrize(
    "fault", ["runs", "subjects", "datasets", "task", "temporal", "chronology", "duplicate"]
)
def test_longitudinal_mismatches_not_silently_aligned(fault):
    a, b = person("a"), person("b")
    if fault == "runs":
        a, b = person(None, "4"), person(None, "8")
    elif fault == "subjects":
        b = person("b", subject="other")
    elif fault == "datasets":
        b = person("b", dataset="other")
    elif fault in ("task", "temporal"):
        d = b.document()
        d["task" if fault == "task" else "temporal_reference"] = (
            "different" if fault == "task" else {"fs_hz": 200}
        )
        b = Identity.from_dict(d)
    elif fault == "duplicate":
        with pytest.raises(ValueError):
            session_audit([a, a])
        return
    r = session_audit([a, b], chronology_required=fault == "chronology")
    assert r["status"] in ("BLOCKED", "INDETERMINATE")
    assert not r["longitudinal_reliability_established"]


def test_source_chronology_overrides_alphabetic_session_labels():
    people = []
    sources = {}
    for session, date in [("z", "2020-01-01T00:00:00Z"), ("a", "2021-01-01T00:00:00Z")]:
        content = json.dumps({"AcquisitionDateTime": date}).encode()
        h = hashlib.sha256(content).hexdigest()
        sources[h] = content
        d = person(session).document()
        d["evidence"].append(h)
        d["chronology"] = {"acquired_at": date, "source_sha256": h}
        people.append(Identity.from_dict(d))
    r = session_audit(people, chronology_required=True, sources=sources)
    assert r["chronology_verified"] and r["chronology"][0]["order"] == "left-before-right"
    sources[next(iter(sources))] = b"changed"
    with pytest.raises(ValueError):
        session_audit(people, chronology_required=True, sources=sources)


@pytest.mark.parametrize("state", ["BLOCKED", "INDETERMINATE", "NOT_APPLICABLE", "READY"])
def test_no_aggregate_override_of_required_gate(state):
    gates = [Gate("ready", "READY", ()), Gate("required", state, ())]
    assert aggregate(gates) == ("READY" if state == "NOT_APPLICABLE" else state)


def prepared(tmp_path, policy=None, review="APPROVED"):
    source = tmp_path / "notice.txt"
    source.write_bytes(CONTENT)
    h = hashlib.sha256(CONTENT).hexdigest()
    i = identity(
        "ibsr-v2",
        "fixture",
        "fictional",
        KEY,
        modality="MRI",
        task="structural",
        hashes=[h],
        spatial={"frame": "native-RAS"},
    )
    selection = Selection(
        i, tmp_path, "fictional", (("image", source),), (("image", h),), b"{}", key=KEY
    )
    p = template("ibsr-v2", "fixture")
    if policy:
        d = p.document()
        d["optional_metadata"] = {
            "research_readiness": {
                "schema": "soma.readiness.policy/1.0.0",
                "analysis": policy,
                "registration_required": True,
                "chronology_required": True,
            }
        }
        p = Protocol.from_dict(d)
    sealed = freeze_cohort(p, [i])
    e = entry()
    e["review"]["status"] = review
    bundle = seal_bundle("ibsr-v2", "fixture", sealed.protocol.fingerprint, [e])
    permission = evidence(
        "ibsr-v2",
        "fixture",
        CONTENT,
        source="fictional-source",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    )
    return sealed, [selection], permission, source, bundle, {"notice": (tmp_path, source.name)}


def test_readiness_recomputes_evidence_and_never_executes(tmp_path):
    args = prepared(tmp_path)
    with patch(
        "soma.workflow.runtime.Executor.run", side_effect=AssertionError("executed science")
    ):
        r = execution_readiness(*args)
    assert r["status"] == "READY" and not r["workflow_execution_authorized_by_report"]
    output = tmp_path / "report"
    write_readiness(r, output)
    assert read_readiness(output / "result.json")["status"] == "READY"
    args[3].write_bytes(b"changed")
    assert execution_readiness(*args)["status"] == "BLOCKED"


@pytest.mark.parametrize("policy", ["longitudinal-descriptive", "confirmatory"])
def test_registration_or_parsing_cannot_authorize_human_inference(tmp_path, policy):
    r = execution_readiness(*prepared(tmp_path, policy))
    assert r["status"] == "BLOCKED"
    assert not r["confirmatory_claim_allowed"]
    assert next(g for g in r["gates"] if g["name"] == "registration")["status"] == "BLOCKED"
    corrupted = copy.deepcopy(r)
    corrupted["status"] = "READY"
    with pytest.raises(ValueError):
        validate_readiness(corrupted)


def test_required_human_review_and_scope_mismatch_retained(tmp_path):
    args = list(prepared(tmp_path, review="REQUIRED"))
    assert execution_readiness(*args)["status"] == "BLOCKED"
    b = args[4].document()
    b["protocol_fingerprint"] = hashlib.sha256(b"other protocol").hexdigest()
    from soma.human.evidence import EvidenceBundle

    args[4] = EvidenceBundle.from_dict(b)
    r = execution_readiness(*args)
    assert next(g for g in r["gates"] if g["name"] == "scope_protocol")["status"] == "BLOCKED"


def test_omitted_individual_gate_cannot_turn_report_ready(tmp_path):
    r = execution_readiness(*prepared(tmp_path))
    r["units"][0]["gates"][0]["status"] = "BLOCKED"
    r["units"][0]["status"] = "BLOCKED"
    with pytest.raises(ValueError):
        validate_readiness(r)


def test_duplicate_recording_content_is_not_independent_measurement(tmp_path):
    from dataclasses import replace

    args = list(prepared(tmp_path))
    selection = args[1][0]
    d = selection.identity.document()
    d["session"] = "different"
    other = replace(selection, identity=Identity.from_dict(d))
    args[0] = freeze_cohort(template("ibsr-v2", "fixture"), [selection.identity, other.identity])
    args[1].append(other)
    from soma.human.evidence import EvidenceBundle

    bundle = args[4].document()
    bundle["protocol_fingerprint"] = args[0].protocol.fingerprint
    args[4] = EvidenceBundle.from_dict(bundle)
    with pytest.raises(ValueError, match="Repeated recording"):
        execution_readiness(*args)


def test_missing_permission_document_retains_blocked_record(tmp_path):
    args = prepared(tmp_path)
    args[3].unlink()
    report = execution_readiness(*args)
    assert report["status"] == "BLOCKED" and len(report["units"]) == 1
    assert report["permission"]["status"] == "BLOCKED"


def test_wrong_frozen_cohort_is_a_blocked_gate_with_selected_units_retained(tmp_path):
    args = list(prepared(tmp_path))
    other = identity(
        "ibsr-v2",
        "fixture",
        "another",
        KEY,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(CONTENT).hexdigest()],
        spatial={"frame": "native-RAS"},
    )
    args[0] = freeze_cohort(template("ibsr-v2", "fixture"), [other])
    report = execution_readiness(*args)
    assert report["status"] == "BLOCKED" and len(report["units"]) == 1
    assert report["units"][0]["status"] == "BLOCKED"


def test_legacy_dispatch_cannot_bypass_readiness_only_protocol(tmp_path):
    from soma.human.workflow import run

    args = prepared(tmp_path, policy="longitudinal-descriptive")
    with patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("bypassed gates")):
        with pytest.raises(ValueError, match="read-only"):
            run(*args[:4], cache=tmp_path / "cache", output=tmp_path / "execution", sequence=1)
    assert not (tmp_path / "execution").exists()
