"""Mock OSF records exercise exact frozen file/version/hash correspondence offline."""

import copy
import hashlib
from unittest.mock import patch

import pytest

from soma.human.registration import OSFAttachments, verify_attachment
from soma.human.workflow import template
from soma.results.contracts import canonical

REG = "abc12"
FILE = "1" * 24


def fixture():
    p = template("ibsr-v2", "fixture")
    content = canonical(p.document())
    record = {
        "registration": {
            "data": {
                "id": REG,
                "type": "registrations",
                "attributes": {
                    "public": True,
                    "withdrawn": False,
                    "archiving": False,
                    "pending_withdrawal": False,
                    "pending_registration_approval": False,
                    "date_registered": "2021-01-02T00:00:00Z",
                },
            }
        },
        "file": {
            "data": {
                "id": FILE,
                "type": "files",
                "attributes": {
                    "provider": "osfstorage",
                    "kind": "file",
                    "current_version": 1,
                    "size": len(content),
                    "extra": {"hashes": {"sha256": hashlib.sha256(content).hexdigest()}},
                },
                "relationships": {
                    "node": {"links": {"related": {"href": f"https://api.osf.io/v2/nodes/{REG}/"}}}
                },
            }
        },
        "version": {
            "data": {
                "id": "1",
                "type": "file_versions",
                "links": {"self": f"https://api.osf.io/v2/files/{FILE}/versions/1/"},
                "attributes": {"size": len(content), "date_created": "2021-01-01T00:00:00Z"},
            }
        },
    }
    return p, content, record


class Mock:
    def __init__(self, record):
        self.record = record

    def retrieve_attachment(self, *args):
        return copy.deepcopy(self.record)


def test_no_network_by_default_and_local_hash_is_not_attestation():
    p, c, r = fixture()
    with patch.object(OSFAttachments, "retrieve_attachment", side_effect=AssertionError("network")):
        assert verify_attachment(p, REG, FILE, "1", c)["status"] == "UNVERIFIED"
    assert verify_attachment(p, REG, FILE, "1", None)["status"] == "NOT_AVAILABLE"
    result = verify_attachment(p, REG, FILE, "1", c, opt_in=True, provider=Mock(r))
    assert result["status"] == "PARTIALLY_VERIFIED" and all(result["checks"].values())
    assert not result["independent_content_timestamp_attestation"]


def test_concrete_adapter_transport_mock_proves_verifier_branch_only():
    p, c, r = fixture()
    # No real registration: fixture intercepts the concrete adapter transport.
    with patch.object(OSFAttachments, "retrieve_attachment", return_value=r):
        result = verify_attachment(p, REG, FILE, "1", c, opt_in=True)
    assert result["status"] == "VERIFIED_IMMUTABLE"
    assert result["independent_content_timestamp_attestation"]
    assert not result["confirmatory_claim_allowed"]


@pytest.mark.parametrize(
    "fault",
    [
        "registration",
        "membership",
        "file",
        "revision",
        "hash",
        "size",
        "withdrawn",
        "archiving",
        "timing",
        "missing",
        "protocol",
        "replaced",
    ],
)
def test_discrepancies_never_verify(fault):
    p, c, r = fixture()
    if fault == "registration":
        r["registration"]["data"]["id"] = "wrong"
    elif fault == "membership":
        r["file"]["data"]["relationships"]["node"]["links"]["related"]["href"] = (
            "https://api.osf.io/v2/nodes/other/"
        )
    elif fault == "file":
        r["file"]["data"]["attributes"]["provider"] = "dropbox"
    elif fault == "revision":
        r["file"]["data"]["attributes"]["current_version"] = 2
    elif fault == "hash":
        r["file"]["data"]["attributes"]["extra"]["hashes"]["sha256"] = hashlib.sha256(
            b"replaced"
        ).hexdigest()
    elif fault == "size":
        r["version"]["data"]["attributes"]["size"] += 1
    elif fault in ("withdrawn", "archiving"):
        r["registration"]["data"]["attributes"][fault] = True
    elif fault == "timing":
        r["version"]["data"]["attributes"]["date_created"] = "2099-01-01T00:00:00Z"
    elif fault == "missing":
        r["file"] = {}
    elif fault == "protocol":
        p = template("eegmmidb", "fixture")
    else:
        c = b"{}"
    with patch.object(OSFAttachments, "retrieve_attachment", return_value=r):
        result = verify_attachment(p, REG, FILE, "1", c, opt_in=True)
    assert result["status"] in ("MISMATCH", "UNVERIFIED", "PARTIALLY_VERIFIED")
    assert not result["independent_content_timestamp_attestation"]


@pytest.mark.parametrize(
    "identifier,file,version",
    [("../x", FILE, "1"), (REG, "../file", "1"), (REG, FILE, "latest"), (REG, FILE, "0")],
)
def test_unsafe_or_unpinned_provider_selectors(identifier, file, version):
    p, c, _ = fixture()
    with pytest.raises(ValueError):
        verify_attachment(p, identifier, file, version, c)


@pytest.mark.parametrize("content", [b"[]", b"null", b"false", b"not json"])
def test_non_object_attachment_is_a_mismatch(content):
    p, _, _ = fixture()
    assert verify_attachment(p, REG, FILE, "1", content)["status"] == "MISMATCH"


def test_missing_immutability_evidence_is_partial_not_a_success():
    p, c, r = fixture()
    del r["registration"]["data"]["attributes"]["archiving"]
    with patch.object(OSFAttachments, "retrieve_attachment", return_value=r):
        result = verify_attachment(p, REG, FILE, "1", c, opt_in=True)
    assert result["status"] == "PARTIALLY_VERIFIED"
    assert not result["independent_content_timestamp_attestation"]
