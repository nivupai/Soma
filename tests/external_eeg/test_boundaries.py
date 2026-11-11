"""Permission, session, labels, epoch timing, blocked outcomes and seal guards."""

import socket

import numpy as np
import pytest
from scipy.io import savemat

from soma.core.provenance import sha256
from soma.external_eeg.contracts import plan, seal_plan
from soma.external_eeg.data import bnci_record, inventory
from soma.external_eeg.runtime import compare, read_receipt, run, write_receipt
from soma.external_eeg.study import evaluate, split_indices
from soma.external_eeg.synthetic import fictional
from soma.human.permissions import PermissionEvidence, evidence


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("External EEG tests cannot download signals")

    monkeypatch.setattr(socket.socket, "connect", denied)


@pytest.fixture
def permission():
    text = b"Fictional research methods permission, no real dataset authorization"
    record = evidence(
        "bnci2014-001",
        "upstream-001-2014-unversioned",
        text,
        source="https://example.org/fictional-evidence",
        license="CC0-1.0",
        supported=True,
    )
    d = record.document()
    d["authority"] = "LOCAL_REVIEW"
    return PermissionEvidence.from_dict(d), text


@pytest.fixture
def mat(tmp_path):
    time = np.arange(8000) / 250
    X = np.column_stack([7 * np.sin(2 * np.pi * (8 + c * 0.4) * time + c) for c in range(25)])
    runs = [
        {
            "X": X,
            "trial": np.array([1, 2001, 4001, 6001]),
            "y": np.array([1, 2, 3, 4]),
            "fs": 250,
            "classes": np.array(["left hand", "right hand", "feet", "tongue"], dtype=object),
            "artifacts": np.zeros(4),
        }
        for _ in range(6)
    ]
    file = tmp_path / "A01T.mat"
    return file, runs


def test_official_mat_units_mapping_and_cue_boundaries(mat, permission):
    file, runs = mat
    savemat(file, {"data": runs})
    perm, text = permission
    d, decisions = bnci_record(
        file, 1, "T", sha256(file), perm, text, "upstream-001-2014-unversioned"
    )
    assert d is not None
    assert d.X.shape == (12, 9, 320)
    assert set(d.y) == {0, 1}
    assert d.metadata.iloc[0].start_sample == 480
    assert d.metadata.iloc[0].stop_sample == 800
    assert np.max(np.abs(d.X)) < 100e-6
    assert sum(r["status"] == "EXCLUDED_NON_BINARY" for r in decisions) == 12
    assert d.metadata.session.eq("T").all()


@pytest.mark.parametrize(
    "fault",
    ["class_order", "labels", "sampling", "missing_channel", "artifacts", "session", "permission"],
)
def test_invalid_raw_records_fail_closed(mat, permission, fault):
    file, runs = mat
    perm, text = permission
    session = "T"
    if fault == "class_order":
        runs[0]["classes"] = np.array(["right hand", "left hand", "feet", "tongue"], dtype=object)
    elif fault == "labels":
        runs[0]["y"] = np.array([0, 1, 2, 3])
    elif fault == "sampling":
        runs[0]["fs"] = 160
    elif fault == "missing_channel":
        runs[0]["X"] = runs[0]["X"][:, :24]
    elif fault == "artifacts":
        runs[0]["artifacts"] = np.zeros(3)
    elif fault == "session":
        session = "E"
    else:
        text = b"changed terms"
    savemat(file, {"data": runs})
    with pytest.raises(ValueError):
        bnci_record(file, 1, session, sha256(file), perm, text, "upstream-001-2014-unversioned")


@pytest.mark.parametrize("split", ["subject", "session"])
def test_plan_split_is_disjoint_and_pairing_audited(split):
    d = fictional()
    p = plan(split=split)
    tr, te = split_indices(d, p)
    assert not set(tr) & set(te)
    if split == "subject":
        assert not set(d.metadata.iloc[tr].subject) & set(d.metadata.iloc[te].subject)
    else:
        assert set(d.metadata.iloc[tr].session) == {"T"} and set(d.metadata.iloc[te].session) == {
            "E"
        }
    d.metadata.loc[0, "session"] = "E"
    with pytest.raises(ValueError, match="pairing"):
        split_indices(d, p)


@pytest.mark.parametrize(
    "fault", ["label_inversion", "source_subjects", "source_sessions", "quality", "parameters"]
)
def test_unapproved_protocol_amendments_fail(fault):
    p = plan()
    sealed = seal_plan(p, "a" * 64, {})
    if fault == "label_inversion":
        p["class_mapping"] = {"1": 1, "2": 0}
    elif fault == "source_subjects":
        p["source_subjects"].append(6)
    elif fault == "source_sessions":
        p["source_sessions"] = ["T"]
    elif fault == "quality":
        p["quality"]["trial_ptp_v"] *= 2
    else:
        p["parameters"]["tangent_lr"]["classifier__C"] = 100
    with pytest.raises(ValueError):
        seal_plan(p, "a" * 64, {})
    from soma.external_eeg.contracts import inspect_plan

    assert inspect_plan(sealed) == plan()


def test_missing_data_never_fits_or_reports_accuracy(tmp_path, monkeypatch):
    root = tmp_path / "raw"
    root.mkdir()
    inv = inventory(root)
    s = seal_plan(plan(), inv["fingerprint"], {})

    def fail(*a, **kw):
        raise AssertionError("Blocked execution attempted fitting")

    monkeypatch.setattr("soma.external_eeg.runtime.evaluate", fail)
    d = run(s, root, tmp_path / "out", None, None, expected_inventory=inv)
    assert d["status"] == "BLOCKED" and d["performance"] == []
    assert read_receipt(tmp_path / "out/result.json")["observed_trials"] == 0
    assert not compare(d, d)["numeric_comparison_authorized"]
    file = root / "A01T.mat"
    file.write_bytes(b"fictional changed inventory")
    with pytest.raises(ValueError, match="inventory"):
        run(s, root, tmp_path / "other", None, None, expected_inventory=inv)


@pytest.mark.parametrize("fault", ["accuracy", "private", "pvalue", "fidelity"])
def test_receipt_rejects_false_claims_and_participant_fields(tmp_path, fault):
    from soma.external_eeg.contracts import candidate_audit

    d = candidate_audit()
    if fault == "accuracy":
        d["performance"] = [{"mean": 0.99}]
    elif fault == "private":
        d["domain_shift"]["subject_key"] = "secret-person"
    elif fault == "pvalue":
        d["p_value"] = 0.001
    else:
        d["original_m22_model"] = True
    write_receipt(d, tmp_path / "report")
    with pytest.raises(ValueError):
        read_receipt(tmp_path / "report/result.json")


def test_missing_targets_are_retained_and_native_models_valid(tmp_path):
    d = fictional()
    p = plan()
    selected = np.flatnonzero(d.metadata.subject != 9)
    d = d.subset(selected)
    report, pred = evaluate(d, p, tmp_path / "models", synthetic=True)
    assert report["status"] == "PARTIAL"
    assert all(
        r["planned_subjects"] == 4 and r["complete_subjects"] == 3 and r["missing_subjects"] == 1
        for r in report["performance"]
    )
    assert len(pred) > 0 and report["p_value"] is None
    assert not report["original_m22_model"]


def test_nd_notice_does_not_automatically_authorize_aggregate_export():
    from soma.human.permissions import check_permission

    text = b"Fictional policy fixture: Four class motor imagery (001-2014) CC BY-ND 4.0"
    p = evidence(
        "bnci2014-001",
        "upstream-001-2014-unversioned",
        text,
        source="https://bnci-horizon-2020.eu/database/data-sets",
        license="CC-BY-ND-4.0",
        supported=True,
    )
    kwargs = dict(
        dataset="bnci2014-001",
        version="upstream-001-2014-unversioned",
        purpose="methods_research",
        source_content=text,
    )
    assert check_permission(p, action="analyze", **kwargs)["allowed"]
    assert not check_permission(p, action="export_aggregate", **kwargs)["allowed"]
    kwargs["source_content"] = b"Changed or missing notice"
    assert not check_permission(p, action="analyze", **kwargs)["allowed"]


@pytest.mark.parametrize("fault", ["missing_bundle", "wrong_protocol", "corrupt_document"])
def test_human_execution_requires_current_m21_bound_review(
    tmp_path, monkeypatch, permission, fault
):
    import hashlib

    from soma.external_eeg import runtime
    from soma.human.evidence import seal_bundle

    perm, text = permission
    root = tmp_path / "raw"
    root.mkdir()
    inv = {"available": 18, "records": [], "fingerprint": "a" * 64}
    monkeypatch.setattr(runtime, "inventory", lambda *a: inv)
    sealed = seal_plan(plan(), inv["fingerprint"], {})
    file = tmp_path / "notice.txt"
    file.write_bytes(text)
    entry = {
        "id": "notice",
        "kind": "agreement",
        "sha256": hashlib.sha256(text).hexdigest(),
        "issuer": "fictional-issuer",
        "source": "fictional-source",
        "document_version": "1",
        "issued_at": "2020-01-01T00:00:00Z",
        "valid_from": "2020-01-01T00:00:00Z",
        "expires_at": None,
        "revoked_at": None,
        "review": {
            "status": "APPROVED",
            "reviewer": "fictional-reviewer",
            "reviewed_at": "2020-01-02T00:00:00Z",
        },
        "purpose": "methods_research",
        "actions": ["analyze", "export_aggregate"],
        "distribution": "AGGREGATE_ONLY",
    }
    bundle = seal_bundle(
        "bnci2014-001",
        plan()["version"],
        "b" * 64 if fault == "wrong_protocol" else sealed.protocol.fingerprint,
        [entry],
        created_at="2020-01-03T00:00:00Z",
    )
    if fault == "corrupt_document":
        file.write_bytes(b"Changed agreement")

    def denied(*a, **kw):
        raise AssertionError("No classifier or signal reader before permission readiness")

    monkeypatch.setattr(runtime, "bnci_record", denied)
    d = runtime.run(
        sealed,
        root,
        tmp_path / "out",
        perm,
        text,
        expected_inventory=inv,
        bundle=None if fault == "missing_bundle" else bundle,
        references={"notice": (tmp_path, file.name)},
    )
    assert d["status"] == "BLOCKED" and d["performance"] == [] and d["blockers"]
