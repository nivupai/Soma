"""Entirely fictional metadata; no data access, identity claim or registration attestation."""

import hashlib

from soma.sdk.human import create_identity, pseudonym, session_match


def run():
    key = bytes(range(32))
    first = create_identity(
        "fictional-dataset",
        "1",
        "fictional-person",
        key,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(b"fictional-source").hexdigest()],
    )
    second = create_identity(
        "another-fictional-dataset",
        "1",
        "fictional-person",
        key,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(b"fictional-source").hexdigest()],
    )
    assert first.document()["session"] is None
    assert not session_match(first, second)["compatible"]
    assert pseudonym("fictional-dataset", "fictional-person", key) != pseudonym(
        "another-fictional-dataset", "fictional-person", key
    )
    return {
        "synthetic_metadata_only": True,
        "absent_session_preserved": True,
        "dataset_identity_collision_rejected": True,
        "external_preregistration_established": False,
    }


if __name__ == "__main__":
    print(run())
