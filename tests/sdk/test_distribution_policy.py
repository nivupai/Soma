"""Distribution scanner rejects unsafe file paths and payloads."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "distribution_policy", Path("scripts/inspect_distributions.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def wheel(tmp_path, extra):
    p = tmp_path / "test.whl"
    with zipfile.ZipFile(p, "w") as z:
        for name in [
            "soma/sdk/imaging.py",
            "services/explorer_api/app.py",
            "soma/py.typed",
            "soma/resources/fmri-inference-policy.yaml",
        ]:
            z.writestr(name, "safe")
        for name, data in extra.items():
            z.writestr(name, data)
    return p


def test_safe_distribution(tmp_path):
    assert module.inspect(wheel(tmp_path, {}))["privacy_passed"]


@pytest.mark.parametrize(
    "name",
    [
        "data/scan.nii.gz",
        "reports/private.json",
        ".env",
        "soma/patient.npz",
        "../escape.py",
        "soma/private.local.json",
        "soma/model.pt",
    ],
)
def test_sensitive_members_rejected(tmp_path, name):
    with pytest.raises(AssertionError):
        module.inspect(wheel(tmp_path, {name: "unsafe"}))


def test_personal_payload_rejected(tmp_path):
    payload = "/" + "Users/" + "example-person/" + "data"
    with pytest.raises(AssertionError):
        module.inspect(wheel(tmp_path, {"soma/extra.py": payload}))
