"""Small reviewed package resources, never local dataset registration files."""

from importlib.resources import files


def inference_policy_text() -> str:
    """Read the bundled human descriptive-only policy without a repository checkout."""
    return files(__package__).joinpath("fmri-inference-policy.yaml").read_text()
