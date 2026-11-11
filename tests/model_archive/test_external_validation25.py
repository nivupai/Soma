"""Opt-in acquisition, immutable frozen inference and scientific rejection boundaries."""

import copy
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

from soma.external_eeg.acquisition import (
    acquire,
    acquisition_template,
    gate,
    snapshot,
    validate_manifest,
)
from soma.external_eeg.validation import (
    M24_RELEASE,
    compare_validation,
    execute,
    harmonization,
    inspect_validation,
    read_validation,
    seal_validation,
    summarize,
)
from soma.human.evidence import seal_bundle
from soma.human.permissions import PermissionEvidence, evidence
from soma.model_archive.archive import numerical_receipt
from soma.workflow.model import digest


def approved(tmp_path):
    m = acquisition_template()
    payload = b"fictional bytes, not human recordings"
    for row in m["files"]:
        row.update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
    notice = b"Fictional distribution review; not real legal evidence"
    (tmp_path / "notice").write_bytes(notice)
    p = evidence(
        m["dataset"],
        m["version"],
        notice,
        source="https://bnci-horizon-2020.eu/database/data-sets",
        license=m["license"],
        supported=True,
    ).document()
    p["authority"] = "LOCAL_REVIEW"
    p = PermissionEvidence.from_dict(p)
    approval = {
        "schema": "soma.acquisition.approval/1",
        "dataset": m["dataset"],
        "version": m["version"],
        "manifest_fingerprint": digest(m),
        "approved": True,
        "terms_acceptance_delegated": False,
    }
    (tmp_path / "approval").write_text(json.dumps(approval))

    def entry(name, kind):
        return {
            "id": name,
            "kind": kind,
            "sha256": hashlib.sha256((tmp_path / name).read_bytes()).hexdigest(),
            "issuer": "fictional-issuer",
            "source": "fictional-source",
            "document_version": "1",
            "issued_at": "2020-01-01T00:00:00Z",
            "valid_from": "2020-01-01T00:00:00Z",
            "expires_at": None,
            "revoked_at": None,
            "review": {
                "status": "APPROVED",
                "reviewer": "fictional-human",
                "reviewed_at": "2020-01-02T00:00:00Z",
            },
            "purpose": "methods_research",
            "actions": ["acquire", "analyze", "export_aggregate"],
            "distribution": "AGGREGATE_ONLY",
        }

    bundle = seal_bundle(
        m["dataset"],
        m["version"],
        "a" * 64,
        [entry("notice", "license"), entry("approval", "agreement")],
    )
    return (
        m,
        p,
        notice,
        bundle,
        {"notice": (tmp_path, "notice"), "approval": (tmp_path, "approval")},
        payload,
    )


def test_no_acquisition_without_explicit_authorization(tmp_path, monkeypatch):
    from soma.external_eeg import acquisition

    m, _, _, _, _, _ = approved(tmp_path)
    monkeypatch.setattr(
        acquisition, "_transfer", lambda *args: pytest.fail("Unauthorized network access")
    )
    with pytest.raises(ValueError, match="Unauthorized"):
        acquire(m, "a" * 64, tmp_path / "raw", tmp_path / "receipt")
    assert not (tmp_path / "raw").exists()


def test_opt_in_acquisition_hashes_and_exclusive_snapshot(tmp_path, monkeypatch):
    from soma.external_eeg import acquisition

    m, p, n, b, refs, payload = approved(tmp_path)
    calls = []

    class Response(io.BytesIO):
        status = 200

        def geturl(self):
            return calls[-1]

    def transfer(url):
        calls.append(url)
        return Response(payload)

    monkeypatch.setattr(acquisition, "_transfer", transfer)
    r = acquire(m, "a" * 64, tmp_path / "raw", tmp_path / "receipt", p, n, b, refs)
    assert r["complete"] and len(calls) == 18 and r["downloaded_files"] == 18
    assert snapshot(tmp_path / "raw", m)["complete"]
    (tmp_path / "raw/A01T.mat").write_bytes(b"changed")
    assert not snapshot(tmp_path / "raw", m)["complete"]
    with pytest.raises(ValueError, match="never overwrites"):
        acquire(m, "a" * 64, tmp_path / "raw", tmp_path / "second", p, n, b, refs)


@pytest.mark.parametrize("fault", ["protocol", "notice", "approval", "expiry", "review", "license"])
def test_evidence_binding_cannot_be_waived(tmp_path, fault):
    m, p, n, b, refs, _ = approved(tmp_path)
    if fault == "protocol":
        protocol = "b" * 64
    else:
        protocol = "a" * 64
    if fault == "notice":
        n = b"changed"
    if fault == "approval":
        (tmp_path / "approval").write_text("{}")
    if fault in {"expiry", "review"}:
        d = b.document()
        d["entries"][1]["expires_at"] = "2021-01-01T00:00:00Z" if fault == "expiry" else None
        if fault == "review":
            d["entries"][1]["review"]["status"] = "REQUIRED"
        b = type(b).from_dict(d)
    if fault == "license":
        d = p.document()
        d["license"] = "CC0-1.0"
        p = PermissionEvidence.from_dict(d)
    assert gate(m, protocol, p, n, b, refs, acquisition=True)["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "fault", ["http", "host", "credentials", "file_order", "missing_hash", "oversize"]
)
def test_distribution_manifest_is_closed(tmp_path, fault):
    m, *_ = approved(tmp_path)
    if fault == "http":
        m["files"][0]["url"] = m["files"][0]["url"].replace("https:", "http:")
    elif fault == "host":
        m["files"][0]["url"] = "https://example.invalid/A01T.mat"
    elif fault == "credentials":
        m["files"][0]["url"] = m["files"][0]["url"].replace("https://", "https://secret@")
    elif fault == "file_order":
        m["files"].reverse()
    elif fault == "missing_hash":
        m["files"][0]["sha256"] = None
    else:
        m["files"][0]["bytes"] = 2**40
    with pytest.raises((ValueError, TypeError)):
        validate_manifest(m)


def test_bad_download_does_not_commit_partial_file(tmp_path, monkeypatch):
    from soma.external_eeg import acquisition

    m, p, n, b, refs, payload = approved(tmp_path)

    class Response(io.BytesIO):
        status = 200

        def geturl(self):
            return m["files"][0]["url"]

    monkeypatch.setattr(acquisition, "_transfer", lambda url: Response(b"x" * len(payload)))
    with pytest.raises(ValueError, match="checksum"):
        acquire(m, "a" * 64, tmp_path / "raw", tmp_path / "out", p, n, b, refs)
    assert not list((tmp_path / "raw").iterdir())


@pytest.mark.parametrize(
    "field",
    [
        "class_mapping",
        "conversion",
        "target_contract",
        "subjects",
        "quality",
        "missing_channels",
        "refitting",
    ],
)
def test_harmonization_amendment_rejected(field):
    from soma.protocol.model import Protocol, seal

    s = seal_validation("a" * 64, M24_RELEASE)
    d = s.protocol.document()
    d["optional_metadata"]["external_validation"][field] = "changed"
    with pytest.raises(ValueError):
        inspect_validation(seal(Protocol.from_dict(d)))


@pytest.fixture(scope="module")
def fixed(tmp_path_factory):
    from examples.external_validation import target
    from soma.external_eeg.synthetic import fictional
    from soma.model_archive.protocol import seal_training
    from soma.model_archive.training import archive_models

    root = tmp_path_factory.mktemp("fixed-transfer")
    release = archive_models(fictional(), seal_training("a" * 64, True), root / "source")
    d = target()
    s = seal_validation(d.fingerprint, release["id"], "synthetic-target-v25")
    return root, release, d, s


def test_independent_synthetic_target_predictions_do_not_refit(fixed, tmp_path):
    root, r, d, s = fixed
    before = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "source").rglob("*")
        if p.is_file()
    }
    report = execute(
        s,
        {},
        tmp_path,
        root / "source/manifest/result.json",
        Path(sys.executable),
        tmp_path / "evaluation",
        synthetic_data=d,
    )
    assert report["status"] == "SYNTHETIC_COMPLETE", (report["model_readiness"], report["prediction_failures"])
    assert report["human_external_trials"] == 0
    assert report["refitted_components"] == 0 and len(report["performance"]) == 5
    assert all(m["complete_subjects"] == 9 for m in report["performance"])
    assert report["performance"][0]["balanced_accuracy"]["mean"] == 0.5
    assert read_validation(tmp_path / "evaluation/summary/result.json")["synthetic_only"]
    assert before == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "source").rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("fault", ["dataset", "session", "channel", "reference", "units", "labels"])
def test_target_identity_and_feature_contract_rejected(fixed, tmp_path, fault):
    from dataclasses import replace

    root, r, data, _ = fixed
    d = copy.deepcopy(data)
    if fault == "dataset":
        d.provenance["dataset"] = "bnci2014-001"
    elif fault == "session":
        d.metadata.loc[0, "session"] = "wrong"
    elif fault == "channel":
        d = replace(d, channels=tuple(reversed(d.channels)))
    elif fault in {"units", "reference"}:
        d.provenance["contract"][{"units": "units", "reference": "reference_scope"}[fault]] = (
            "wrong"
        )
    else:
        d.y[0] = 1 - d.y[0]
    s = seal_validation(data.fingerprint, r["id"], "synthetic-target-v25")
    with pytest.raises(ValueError):
        execute(
            s,
            {},
            tmp_path,
            root / "source/manifest/result.json",
            Path(sys.executable),
            tmp_path / "bad",
            synthetic_data=d,
        )


def test_missing_people_and_models_remain_missing(fixed, tmp_path):
    _, _, d, _ = fixed
    p = harmonization("synthetic-target-v25")
    p["subjects"].append(10)
    values = {"dummy_labels": d.y.copy()}
    rows = summarize(d, values, p, tmp_path / "units")
    assert rows[0]["missing_subjects"] == 1 and rows[0]["balanced_accuracy"]["unit"] == "subject"
    assert rows[1]["prediction_coverage"] == 0 and rows[1]["missing_subjects"] == 10
    assert (
        compare_validation(
            {"dataset": "eegmmidb", "status": "COMPLETE"},
            {"dataset": "bnci2014-001", "status": "BLOCKED"},
        )["status"]
        == "NOT_COMPARABLE"
    )


def test_private_export_and_fake_human_results_rejected(tmp_path):
    from services.explorer_api.external_validation import demo

    for key, value in [
        ("performance", [{"subject": 1}]),
        ("human_external_trials", 1),
        ("independent_replication", True),
    ]:
        d = demo()
        d.update(independent_replication=False, confirmatory_claim_allowed=False)
        d[key] = value
        out = tmp_path / key
        numerical_receipt(d, {}, out, "soma.external-validation")
        with pytest.raises(ValueError):
            read_validation(out / "result.json")


def test_unapproved_human_execution_does_not_read_snapshot_or_launch_worker(
    fixed, tmp_path, monkeypatch
):
    from soma.external_eeg import validation

    _, release, _, _ = fixed
    fake = copy.deepcopy(release)
    fake["id"] = M24_RELEASE
    monkeypatch.setattr(validation, "inspect_archive", lambda *args: fake)
    monkeypatch.setattr(validation, "snapshot", lambda *args: pytest.fail("Unapproved raw read"))
    monkeypatch.setattr(
        validation, "runtime_request", lambda *args: pytest.fail("Unapproved inference")
    )
    m, *_ = approved(tmp_path)
    s = seal_validation(digest(m), M24_RELEASE)
    report = execute(
        s,
        m,
        tmp_path / "absent-raw",
        tmp_path / "unused",
        Path(sys.executable),
        tmp_path / "blocked",
    )
    assert (
        report["status"] == "BLOCKED"
        and report["human_external_trials"] == 0
        and report["performance"] == []
    )
    assert (
        read_validation(tmp_path / "blocked/summary/result.json")["scientific_compatibility"]
        == "NOT_COMPARABLE"
    )


def test_aggregate_reader_rejects_arrays_before_loading_them(tmp_path):
    import numpy as np

    from services.explorer_api.external_validation import demo

    d = demo()
    d.update(independent_replication=False, confirmatory_claim_allowed=False)
    numerical_receipt(d, {"private": np.ones(3)}, tmp_path / "bad", "soma.external-validation")
    for f in (tmp_path / "bad/arrays").glob("*"):
        f.unlink()
    with pytest.raises(ValueError, match="Only aggregate"):
        read_validation(tmp_path / "bad/result.json")


def test_unverified_metadata_is_not_promoted_to_a_feature_contract():
    cho = harmonization("cho2017")
    small = harmonization("bnci2014-004")
    assert cho["target_contract"] is None and cho["conversion"]["input_units"] is None
    assert small["target_contract"] is None and small["target_observation"]["eeg_channels"] == 3
    assert not cho["compatible"] and not small["compatible"]
    assert not harmonization(mode="EXACT_FROZEN")["technical_harmonization_allowed"]
