"""Reuse the frozen M14 synthetic fixture; no medical files or external processes."""

import hashlib
import json
from dataclasses import replace

import pytest

from soma.core.provenance import sha256
from soma.human.adapters import Selection, identity
from soma.human.preprocessing import PreprocessingManifest, manifest_from_bundle
from soma.results.contracts import canonical
from tests.fmri14.conftest import bundle as bundle


@pytest.fixture
def imported(bundle):
    source = dict(bundle.evidence)
    source["distortion_correction_source"] = "synthetic fixture: no distortion simulated"
    bundle = replace(bundle, evidence=source)
    key = bytes(range(32))
    files = (
        ("image", bundle.raw_bold),
        ("structural", bundle.raw_root / "sub-01/ses-test/anat/sub-01_ses-test_T1w.nii.gz"),
    )
    hashes = tuple((k, sha256(p)) for k, p in files)
    person = identity(
        "ds000114",
        "1.0.2",
        "01",
        key,
        modality="fMRI",
        task="motor",
        run="1",
        session="test",
        hashes=[v for _, v in hashes],
        temporal={"tr_s": 2.0},
    )
    selection = Selection(person, bundle.raw_root, "01", files, hashes, b"{}", key=key)
    manifest = manifest_from_bundle(
        bundle,
        person.fingerprint,
        configuration={"fixture": True},
        environment={"fixture": "no actual fMRIPrep execution"},
        distortion_correction="NOT_REQUIRED",
        bids_validation="PASS",
    )
    value = manifest.document()
    report = bundle.derivative_root / "synthetic-bids-report.json"
    snapshot = hashlib.sha256(
        canonical({k: a["sha256"] for k, a in value["assets"].items() if a["root"] == "raw"})
    ).hexdigest()
    report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "validator": "synthetic-fixture",
                "version": "1",
                "input_snapshot_sha256": snapshot,
            }
        )
    )
    value["assets"]["bids-report"] = {
        "root": "derivatives",
        "path": report.name,
        "sha256": sha256(report),
    }
    return (
        PreprocessingManifest.from_dict(value),
        selection,
        {"raw": bundle.raw_root, "derivatives": bundle.derivative_root},
        bundle,
    )


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """All M21 CI tests must work without any network connection."""
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("Readiness fixtures must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
