"""Small reviewed package resources, never local dataset registration files."""

from importlib.resources import files


def inference_policy_text() -> str:
    """Read the bundled human descriptive-only policy without a repository checkout."""
    return files(__package__).joinpath("fmri-inference-policy.yaml").read_text()


def protocol_document_sha256(name: str) -> str:
    """Hash a frozen document, preserving source tamper checks and installed use."""
    import hashlib
    from pathlib import Path

    if name not in {"REPLICATION_PROTOCOL.md", "DECODING_PROTOCOL.md"}:
        raise ValueError("Unknown packaged protocol document")
    root = Path(__file__).resolve().parents[3]
    if (root / "src/soma/resources/__init__.py").is_file():
        content = (root / "docs" / name).read_bytes()
    else:
        content = files(__package__).joinpath(name).read_bytes()
    return hashlib.sha256(content).hexdigest()
