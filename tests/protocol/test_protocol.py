"""Adversarial frozen declarations and structural scientific version comparisons."""

import copy
import json
from dataclasses import FrozenInstanceError

import pytest

from soma.protocol.binding import (
    Snapshot,
    conformance,
    example_protocol,
    example_snapshot,
    graph_for,
)
from soma.protocol.examples import method_amendment
from soma.protocol.model import (
    Protocol,
    ProtocolError,
    amend,
    compare_protocols,
    read_seal,
    seal,
    write_seal,
)
from soma.workflow.model import Graph


@pytest.mark.parametrize("family", ["eeg", "mri", "fmri", "source"])
def test_seal_immutable_reproducible_and_not_preregistration(family, tmp_path):
    p = example_protocol(family)
    s = seal(p)
    assert s._canonical == seal(Protocol.from_dict(p.document()))._canonical
    assert not s.record()["validation_receipt"]["external_preregistration_verified"]
    d = p.document()
    d["scientific"]["estimand"] = "mutated copy"
    assert p.document()["scientific"]["estimand"] != "mutated copy"
    with pytest.raises(FrozenInstanceError):
        p._canonical = b"changed"
    path = tmp_path / "seal.json"
    write_seal(s, path)
    assert read_seal(path).protocol.fingerprint == p.fingerprint
    with pytest.raises(FileExistsError):
        write_seal(s, path)
    data = json.loads(path.read_text())
    data["protocol"]["scientific"]["objective"] = "tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(ProtocolError):
        read_seal(path)


@pytest.mark.parametrize(
    "field",
    [
        "question",
        "objective",
        "estimand",
        "population",
        "preprocessing",
        "analysis_methods",
        "inference",
        "qc",
        "limitations",
    ],
)
def test_missing_scientific_fields_rejected(field):
    d = example_protocol("eeg").document()
    del d["scientific"][field]
    with pytest.raises(ProtocolError):
        Protocol.from_dict(d)


@pytest.mark.parametrize(
    "mutation",
    [
        "no-inclusion",
        "trial-unit",
        "confirmatory",
        "inference-claim",
        "unimplemented-correction",
        "negative-tolerance",
        "nan-tolerance",
        "missing-metadata-policy",
        "qc-selective",
        "unknown-schema",
    ],
)
def test_unsafe_scientific_policies(mutation):
    d = example_protocol("fmri").document()
    if mutation == "no-inclusion":
        d["scientific"]["population"]["inclusion"] = []
    elif mutation == "trial-unit":
        d["scientific"]["population"]["unit"] = "trial"
    elif mutation == "confirmatory":
        d["scientific"]["inference"]["mode"] = "confirmatory"
    elif mutation == "inference-claim":
        d["scientific"]["inference"]["confirmatory_claim_allowed"] = True
    elif mutation == "unimplemented-correction":
        d["scientific"]["inference"]["correction"] = "automatic"
    elif mutation == "negative-tolerance":
        d["tolerances"]["atol"] = -1
    elif mutation == "nan-tolerance":
        d["tolerances"]["atol"] = float("nan")
    elif mutation == "missing-metadata-policy":
        d["tolerances"]["missing_policy"] = "zero-fill"
    elif mutation == "qc-selective":
        d["scientific"]["qc"]["exclusion_policy"] = "best outcomes only"
    else:
        d["schema"] = "soma.protocol/99.0.0"
    with pytest.raises(ProtocolError):
        Protocol.from_dict(d)


def test_semantic_revision_not_version_string_compatibility():
    p = example_protocol("eeg")
    d = p.document()
    d["version"] = "1.0.1"
    d["scientific"]["estimand"] = "different quantity"
    q = Protocol.from_dict(d)
    diff = compare_protocols(p, q)
    assert (
        diff["scientific_change"]
        and diff["major_revision_required"]
        and not diff["version_declaration_valid"]
    )
    assert not diff["compatible_scientific_methods"]
    with pytest.raises(ProtocolError):
        amend(p, d, reason="posthoc", authorization_reference="local")
    d["version"] = "2.0.0"
    q = amend(
        p,
        d,
        reason="new scientific objective",
        authorization_reference="local",
        outcome_inspection="yes",
    )
    assert compare_protocols(p, q)["explicit_parent_amendment"]
    assert q.document()["amendment"]["timing_evidence"] == "LOCAL_UNVERIFIED"


def test_editorial_optional_revision_preserves_scientific_identity():
    p = example_protocol("mri")
    d = p.document()
    d.update(
        version="1.0.1", editorial="clarified wording", optional_metadata={"citation": "declared"}
    )
    q = amend(p, d, reason="editorial", authorization_reference="local")
    assert p.fingerprint != q.fingerprint and p.scientific_fingerprint == q.scientific_fingerprint
    assert compare_protocols(p, q)["compatible_scientific_methods"]


@pytest.mark.parametrize("family", ["eeg", "mri", "fmri", "source"])
def test_explicit_scientific_amendments_bind_methods(family):
    p = example_protocol(family)
    q = method_amendment(p, family)
    assert compare_protocols(p, q)["scientific_change"]
    snap = example_snapshot(p)
    member = snap.document()["members"][0]
    assert conformance(p, graph_for(q, snap, member))["status"] == "NONCONFORMANT"
    assert (
        conformance(q, graph_for(q, snap, member), snapshot=snap, member=member)["status"]
        == "CONFORMANT"
    )


@pytest.mark.parametrize(
    "change", ["reference", "ontology", "frame", "seed", "hrf", "unknown-implementation"]
)
def test_unauthorized_workflow_overrides(change):
    family = (
        "eeg"
        if change in {"reference", "seed"}
        else "mri"
        if change in {"ontology", "frame"}
        else "fmri"
    )
    p = example_protocol(family)
    snap = example_snapshot(p)
    member = snap.document()["members"][0]
    g = graph_for(p, snap, member).to_dict()
    if change == "reference":
        next(s for s in g["stages"] if s["id"] == "reference")["parameters"]["reference"] = "none"
    elif change == "seed":
        next(s for s in g["stages"] if s["id"] == "generate")["seed"] += 1
    elif change == "ontology":
        next(a for a in g["artifacts"] if a["kind"] == "mri.labels")["metadata"]["ontology"][
            "1"
        ] = "human-WM"
    elif change == "frame":
        g["artifacts"][0]["metadata"]["spatial_reference"]["frame"] = "LPS"
    elif change == "hrf":
        next(s for s in g["stages"] if s["id"] == "model")["parameters"]["hrf_model"] = "glover"
    else:
        g["stages"][0]["implementation"] = "os.system"
    result = conformance(p, Graph.from_dict(g), snapshot=snap, member=member)
    assert result["status"] == "NONCONFORMANT" and result["deviations"]
    assert all(d["resolution_status"] == "UNAPPROVED" for d in result["deviations"])


@pytest.mark.parametrize(
    "mutation",
    ["missing-snapshot-id", "duplicate-unit", "unknown-availability", "unapproved-removal-reason"],
)
def test_snapshot_and_sampling_integrity(mutation):
    s = example_snapshot(example_protocol("eeg")).document()
    if mutation == "missing-snapshot-id":
        del s["id"]
    elif mutation == "duplicate-unit":
        s["members"].append(copy.deepcopy(s["members"][0]))
    elif mutation == "unknown-availability":
        s["members"][0]["available"] = "maybe"
    else:
        s["members"][0].update(available=False, reason="unfavorable effect")
    with pytest.raises(ProtocolError):
        Snapshot.from_dict(s)


@pytest.mark.parametrize("field", ["axes", "units"])
def test_outcome_axes_cannot_be_relabeled_as_another_quantity(field):
    p = example_protocol("eeg")
    d = p.document()
    d["tolerances"][field][0] = "different-outcome"
    if field == "axes":
        d["scientific"]["primary_outcomes"][0] = "different-outcome"
    q = Protocol.from_dict(d)
    s = example_snapshot(q)
    m = s.document()["members"][0]
    assert conformance(q, graph_for(q, s, m))["status"] == "NONCONFORMANT"


def test_unsupported_eligibility_is_never_executed():
    from soma.protocol.binding import example_snapshot, graph_for

    d = example_protocol("eeg").document()
    d["scientific"]["population"]["inclusion"] = ["retain only favorable outcomes"]
    p = Protocol.from_dict(d)
    snapshot = example_snapshot(p)
    with pytest.raises(ProtocolError, match="Eligibility"):
        graph_for(p, snapshot, snapshot.document()["members"][0])
