"""Deterministic adversarial metadata fixtures, not human data or legal attestation."""

import hashlib
import json
from unittest.mock import patch

import pytest

from soma.human.adapters import Selection, identity
from soma.human.model import Identity, pseudonym, session_match, validate_cohort
from soma.human.permissions import PermissionEvidence, check_permission, evidence
from soma.human.registration import inspect_registration, verify_registration
from soma.human.workflow import conformance, freeze_cohort, plan, read_execution, run, template
from soma.protocol.model import Protocol, ProtocolError

KEY = bytes(range(32))
NOTICE = b"Synthetic test fixture: Torsten Rohlfing public domain release notice"


def person(dataset="ibsr-v2", subject="fictional-01", session=None, task="structural", run_id=None):
    return identity(
        dataset,
        "v2-stripped",
        subject,
        KEY,
        modality="MRI",
        task=task,
        hashes=[hashlib.sha256(NOTICE).hexdigest()],
        session=session,
        run=run_id,
    )


def permission():
    p = evidence(
        "ibsr-v2",
        "v2-stripped",
        NOTICE,
        source="synthetic-fixture-notice",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    )
    d = p.document()
    d["reviewed_at"] = "2020-01-01T00:00:00+00:00"
    return PermissionEvidence.from_dict(d)


def selection(tmp_path, who=None):
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    return Selection(
        who or person(),
        source,
        "fictional-01",
        (),
        (),
        b'{"preprocessing":"fictional metadata only"}',
    )


def test_dataset_scope_and_immutable_canonical_identity():
    a, b = person(), person("another-dataset")
    assert a.document()["subject"] != b.document()["subject"]
    assert a.participant != b.participant and not session_match(a, b)["compatible"]
    d = a.document()
    d["task"] = "mutated"
    assert a.document()["task"] == "structural"
    assert a.fingerprint == Identity.from_dict(a.document()).fingerprint
    with pytest.raises(ProtocolError):
        pseudonym("dataset", "subject", b"short")


@pytest.mark.parametrize("field", ["session", "task", "run", "acquisition", "dataset", "version"])
def test_wrong_record_pairings_are_rejected(field):
    a = person()
    d = a.document()
    d[field] = "different"
    b = Identity.from_dict(d)
    assert not session_match(a, b)["compatible"]


@pytest.mark.parametrize("field", ["session", "run", "acquisition"])
def test_absent_entities_are_not_invented(field):
    a = person()
    assert a.document()[field] is None
    d = a.document()
    d[field] = "1"
    assert not session_match(a, Identity.from_dict(d))["compatible"]
    assert not session_match(a, a)["chronology_verified"]


@pytest.mark.parametrize(
    "mutation", ["schema", "raw-subject", "missing-evidence", "invalid-date", "trial-unit"]
)
def test_identity_schema_integrity(mutation):
    d = person().document()
    if mutation == "schema":
        d["schema"] = "unknown"
    elif mutation == "raw-subject":
        d["subject"] = "real-patient-name"
    elif mutation == "missing-evidence":
        d["evidence"] = []
    elif mutation == "invalid-date":
        d["chronology"] = {"acquired_at": "test-session", "source_sha256": d["evidence"][0]}
    else:
        d["consent_evidence"] = "inferred from file possession"
    with pytest.raises((ValueError, TypeError)):
        Identity.from_dict(d)


def test_duplicate_participants_and_independent_recordings():
    a = person()
    with pytest.raises(ProtocolError):
        validate_cohort([a, a])
    validate_cohort([a, person(session="different")])


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "revoked",
        "conflict",
        "expired",
        "future-review",
        "purpose",
        "dataset",
        "version",
        "source",
        "license",
        "redistribute",
        "export-records",
    ],
)
def test_permission_refusal(mutation):
    d = permission().document()
    content = NOTICE
    action = "analyze"
    purpose = "methods_research"
    if mutation in ["unknown", "revoked", "conflict"]:
        d["review_status"] = mutation.upper()
    elif mutation == "expired":
        d["expires_at"] = "2021-01-01T00:00:00+00:00"
    elif mutation == "future-review":
        d["reviewed_at"] = "2099-01-01T00:00:00+00:00"
    elif mutation == "purpose":
        purpose = "commercial-resale"
    elif mutation == "dataset":
        d["dataset"] = "another-dataset"
    elif mutation == "version":
        d["version"] = "another-version"
    elif mutation == "source":
        content = b"changed"
    elif mutation == "license":
        d["license"] = "unrestricted-everything"
    elif mutation == "redistribute":
        action = "redistribute"
    else:
        action = "export_records"
    result = check_permission(
        PermissionEvidence.from_dict(d),
        dataset="ibsr-v2",
        version="v2-stripped",
        purpose=purpose,
        action=action,
        source_content=content,
        at="2026-01-01T00:00:00+00:00",
    )
    assert not result["allowed"] and result["reasons"]
    assert not result["legal_authorization_established"] and not result["consent_verified"]


def test_content_bound_permission_is_explicit_and_not_consent():
    result = check_permission(
        permission(),
        dataset="ibsr-v2",
        version="v2-stripped",
        purpose="methods_research",
        action="analyze",
        source_content=NOTICE,
        at="2026-01-01T00:00:00+00:00",
    )
    assert result["allowed"] and not result["consent_verified"]


def test_frozen_cohort_cannot_drop_records_after_inspection(tmp_path):
    a, b = selection(tmp_path), selection(tmp_path, person(subject="fictional-02"))
    sealed = freeze_cohort(template("ibsr-v2", "v2-stripped"), [a.identity, b.identity])
    source = tmp_path / "notice.txt"
    source.write_bytes(NOTICE)
    assert len(plan(sealed, [a, b], permission(), source)["units"]) == 2
    with pytest.raises(ValueError, match="Frozen cohort"):
        plan(sealed, [a], permission(), source)
    with pytest.raises(ValueError):
        freeze_cohort(sealed.protocol, [a.identity])


@pytest.mark.parametrize(
    "override", ["estimand", "population-unit", "inference", "method", "ontology"]
)
def test_scientific_overrides_not_authorized(tmp_path, override):
    p = template("ibsr-v2", "v2-stripped")
    d = p.document()
    if override == "estimand":
        d["scientific"]["estimand"] = "another quantity"
    elif override == "population-unit":
        d["scientific"]["population"]["unit"] = "trial"
    elif override == "inference":
        d["scientific"]["inference"]["confirmatory_claim_allowed"] = True
    elif override == "method":
        d["scientific"]["preprocessing"]["analysis"]["threshold_tuning"] = True
    else:
        d["scientific"]["anatomical_conventions"]["summary"]["units"] = {"summary": "mm"}
    try:
        q = Protocol.from_dict(d)
    except ProtocolError:
        return
    assert conformance(q, selection(tmp_path), permission(), NOTICE)["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "run_id,task", [("3", "unilateral-movement"), ("6", "bilateral-imagery"), ("1", "baseline")]
)
def test_eeg_execution_imagery_confusion(run_id, task, tmp_path):
    who = identity(
        "eegmmidb",
        "1.0.0",
        "fictional-01",
        KEY,
        modality="EEG",
        task=task,
        run=run_id,
        hashes=["0" * 64],
    )
    s = selection(tmp_path, who)
    assert (
        conformance(template("eegmmidb", "1.0.0"), s, permission(), NOTICE)["status"] == "BLOCKED"
    )


def test_mrbrains_partition_and_fmri_preprocessing_are_blocked(tmp_path):
    for dataset, modality, partition in [
        ("mrbrains13", "MRI", "test"),
        ("ds000114", "fMRI", "development"),
    ]:
        who = identity(
            dataset,
            "fixture",
            "fictional-01",
            KEY,
            modality=modality,
            task="structural",
            hashes=["0" * 64],
            partition=partition,
        )
        s = selection(tmp_path, who)
        report = conformance(template(dataset, "fixture"), s, permission(), NOTICE)
        assert report["status"] == "BLOCKED" and report["reasons"]


def test_blocked_record_is_native_metadata_without_running_science(tmp_path):
    s = selection(tmp_path)
    sealed = freeze_cohort(template("ibsr-v2", "v2-stripped"), [s.identity])
    source = tmp_path / "notice.txt"
    source.write_bytes(NOTICE)
    d = permission().document()
    d["review_status"] = "REVOKED"
    revoked = PermissionEvidence.from_dict(d)
    with patch(
        "soma.workflow.runtime.Executor.run", side_effect=AssertionError("Unauthorized science")
    ):
        r = run(
            sealed,
            [s],
            revoked,
            source,
            cache=tmp_path / "cache",
            output=tmp_path / "record",
            sequence=1,
        )
    assert r["units"][0]["status"] == "BLOCKED"
    actual = read_execution(tmp_path / "record/result.json")
    assert len(actual["units"]) == 1 and not actual["human_reliability_authorized"]
    assert str(tmp_path) not in json.dumps(actual)
    file = tmp_path / "record/result.json"
    data = json.loads(file.read_text())
    data["payload"]["values"]["sequence"] = 2
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_execution(file)


class FixtureProvider:
    def __init__(self, protocol):
        self.protocol = protocol

    def retrieve(self, identifier):
        return {
            "data": {
                "id": identifier,
                "type": "registrations",
                "attributes": {
                    "public": True,
                    "withdrawn": False,
                    "date_registered": "2020-01-01T00:00:00+00:00",
                    "description": "soma_protocol_id="
                    + self.protocol.document()["id"]
                    + " soma_protocol_fingerprint="
                    + self.protocol.fingerprint,
                },
            }
        }


def test_external_registration_requires_opt_in_and_real_provider():
    p = template("ibsr-v2", "v2-stripped")
    with patch(
        "soma.human.registration.OSF.retrieve", side_effect=AssertionError("Network without opt-in")
    ):
        assert verify_registration(p, "abcde")["status"] == "UNVERIFIED"
    result = verify_registration(p, "abcde", opt_in=True, provider=FixtureProvider(p))
    assert result["status"] == "UNVERIFIED" and result["registration_timestamp"].startswith("2020")
    assert not result["independent_preregistration_established"]
    assert (
        inspect_registration({"status": "VERIFIED", "fingerprint": "tampered"}, p)["status"]
        == "UNVERIFIED"
    )


@pytest.mark.parametrize(
    "change", ["fingerprint", "id", "withdrawn", "private", "future", "missing-date"]
)
def test_invalid_external_claims(change):
    p = template("ibsr-v2", "v2-stripped")
    record = FixtureProvider(p).retrieve("abcde")
    a = record["data"]["attributes"]
    if change == "fingerprint":
        a["description"] = a["description"].replace(p.fingerprint, "0" * 64)
    elif change == "id":
        record["data"]["id"] = "other"
    elif change == "withdrawn":
        a["withdrawn"] = True
    elif change == "private":
        a["public"] = False
    elif change == "future":
        a["date_registered"] = "2099-01-01T00:00:00+00:00"
    else:
        del a["date_registered"]
    with patch("soma.human.registration.OSF.retrieve", return_value=record):
        assert verify_registration(p, "abcde", opt_in=True)["status"] == "UNVERIFIED"


def test_editable_public_metadata_match_is_not_immutable_registration():
    p = template("ibsr-v2", "v2-stripped")
    data = FixtureProvider(p).retrieve("abcde")
    with patch("soma.human.registration.OSF.retrieve", return_value=data):
        receipt = verify_registration(p, "abcde", opt_in=True)
    assert receipt["status"] == "PARTIAL_PUBLIC_METADATA_MATCH"
    assert not receipt["content_timestamp_attested"]
    assert not receipt["registered_content_immutability_verified"]
    assert not receipt["independent_preregistration_established"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "/private/clinical/terms.txt"),
        ("source", "https://example.org/?token=private"),
        ("agreement_id", "file:///private/agreement"),
        ("restrictions", ["read /private/clinical/terms.txt"]),
    ],
)
def test_private_locations_and_credentials_rejected_from_permission_evidence(field, value):
    d = permission().document()
    d[field] = value
    with pytest.raises(ValueError):
        PermissionEvidence.from_dict(d)


def test_private_mapping_verified_in_memory_and_never_dispatched(tmp_path):
    from dataclasses import replace

    from soma.human.workflow import graph_for

    s = replace(selection(tmp_path), key=KEY)
    s.verify_inputs()
    with pytest.raises(ValueError, match="mapping"):
        replace(s, subject="fictional-02").verify_inputs()
    source = tmp_path / "notice.txt"
    source.write_bytes(NOTICE)
    sealed = freeze_cohort(template("ibsr-v2", "v2-stripped"), [s.identity])
    graph, context = graph_for(sealed.protocol, s, permission(), source)
    assert KEY.hex() not in json.dumps(context)
    assert KEY.hex() not in json.dumps(graph.to_dict())
    assert "key" not in context and "pseudonym_key" not in context


def test_missing_selected_unit_is_retained_in_denominator(tmp_path):
    from dataclasses import replace

    a = replace(selection(tmp_path), key=KEY)
    d = person(subject="fictional-02").document()
    d["availability"] = "MISSING"
    b = replace(selection(tmp_path, Identity.from_dict(d)), subject="fictional-02", key=KEY)
    sealed = freeze_cohort(template("ibsr-v2", "v2-stripped"), [a.identity, b.identity])
    source = tmp_path / "notice.txt"
    source.write_bytes(NOTICE)
    report = plan(sealed, [a, b], permission(), source)
    assert len(report["units"]) == 2 and report["units"][1]["eligibility"]["status"] == "BLOCKED"
    assert report["units"][1]["identity"]["availability"] == "MISSING"


def test_record_exports_remain_unsupported_even_if_asserted():
    d = permission().document()
    d["actions"].extend(["export_records", "redistribute"])
    for action in ["export_records", "redistribute"]:
        result = check_permission(
            PermissionEvidence.from_dict(d),
            dataset="ibsr-v2",
            version="v2-stripped",
            purpose="methods_research",
            action=action,
            source_content=NOTICE,
        )
        assert not result["allowed"]


@pytest.mark.parametrize("bad", ["frame", "invented-session", "sampling"])
def test_acquisition_and_spatial_conformance(bad, tmp_path):
    from dataclasses import replace

    if bad == "sampling":
        who = identity(
            "eegmmidb",
            "1.0.0",
            "fictional-01",
            KEY,
            modality="EEG",
            task="unilateral-imagery",
            run="4",
            hashes=["0" * 64],
            acquisition={"channels": 64, "sfreq_hz": 80.0},
            temporal={"unit": "s", "fs_hz": 80.0},
        )
    else:
        d = person().document()
        d["spatial_reference"] = {"frame": "LPS" if bad == "frame" else "native-RAS"}
        if bad == "invented-session":
            d["session"] = "1"
        who = Identity.from_dict(d)
    selected = replace(selection(tmp_path, who), key=KEY)
    d = who.document()
    assert (
        conformance(template(d["dataset"], d["version"]), selected, permission(), NOTICE)["status"]
        == "BLOCKED"
    )


def test_fmri_cannot_be_unblocked_by_relabeling_modality(tmp_path):
    who = identity(
        "ds000114",
        "1.0.2",
        "fictional-01",
        KEY,
        modality="MRI",
        task="structural",
        hashes=["0" * 64],
    )
    source = json.dumps(
        {"License": "CC0", "DatasetDOI": "doi:10.18112/openneuro.ds000114.v1.0.2"}
    ).encode()
    use = evidence(
        "ds000114",
        "1.0.2",
        source,
        source="synthetic-local-description",
        license="CC0",
        supported=True,
    )
    result = conformance(template("ds000114", "1.0.2"), selection(tmp_path, who), use, source)
    assert result["permission"]["allowed"]
    assert result["status"] == "BLOCKED"
    assert any("human GLM blocked" in reason for reason in result["reasons"])


def test_configuration_never_coerces_boolean_subject_to_participant_one(tmp_path):
    from soma.human.configuration import request

    path = tmp_path / "request.local.json"
    path.write_text(
        json.dumps(
            {
                "dataset": "eegmmidb",
                "root": "unused",
                "subjects": [True],
                "runs": ["4"],
                "key_file": "unused",
                "permission_file": "unused",
                "permission_source": "unused",
                "seal_file": "unused",
            }
        )
    )
    with pytest.raises(ValueError, match="Subject selectors"):
        request(path)


def test_outputs_cannot_be_written_into_source_dataset(tmp_path):
    from dataclasses import replace

    s = replace(selection(tmp_path), key=KEY)
    protocol = freeze_cohort(template("ibsr-v2", "v2-stripped"), [s.identity])
    source = tmp_path / "notice.txt"
    source.write_bytes(NOTICE)
    with pytest.raises(ValueError, match="input dataset root"):
        run(
            protocol,
            [s],
            permission(),
            source,
            cache=s.root / "cache",
            output=tmp_path / "record",
            sequence=1,
        )
    assert not (s.root / "cache").exists()
