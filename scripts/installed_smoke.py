"""Run with installed Python from an isolated cwd, with no repository import path."""

import argparse
import importlib
import json
import sys
from importlib.metadata import metadata, version
from pathlib import Path

from packaging.specifiers import SpecifierSet

import soma
from soma.resources import inference_policy_text
from soma.sdk.provenance import manifest

parser = argparse.ArgumentParser()
parser.add_argument("--expected-version", required=True)
parser.add_argument("--explorer", action="store_true")
args = parser.parse_args()
assert soma.__version__ == version("soma-neuro") == args.expected_version
assert Path(soma.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert SpecifierSet(metadata("soma-neuro")["Requires-Python"]) == SpecifierSet(">=3.11,<3.13")
for module in [
    "imaging",
    "eeg",
    "source",
    "fmri",
    "provenance",
    "synthetic",
    "results",
    "workflow",
    "protocol",
    "human",
    "readiness",
    "eeg_benchmark",
]:
    importlib.import_module("soma.sdk." + module)
assert "descriptive_only" in inference_policy_text()
assert manifest({"synthetic": True}, {}, {})["git_revision"] is None
if "--explorer" in sys.argv:
    from fastapi.testclient import TestClient

    from soma.sdk.explorer import create_app

    with TestClient(create_app(), base_url="http://127.0.0.1") as c:
        for path in [
            "/api/catalog",
            "/api/eeg-benchmarks",
            "/api/external-eeg/demo-external-eeg",
            "/api/eeg-benchmarks/demo-eeg-benchmark",
            "/api/experiments",
            "/api/experiments/demo-calibration/export?format=json",
            "/api/eeg/demo-eeg/analysis",
            "/api/volumes/demo-mri",
            "/api/sources/demo-source/mesh",
            "/api/fmri/demo-fmri",
        ]:
            r = c.get(path)
            assert r.status_code == 200, (path, r.text)
            assert "/Users/" not in r.text
else:
    assert importlib.util.find_spec("fastapi") is None
    from soma.sdk.explorer import create_app

    try:
        create_app()
    except ImportError as error:
        assert "[explorer]" in str(error)
    else:
        raise AssertionError("Core install unexpectedly has optional Explorer")
print(
    json.dumps(
        {
            "version": version("soma-neuro"),
            "installed_in_environment": True,
            "explorer": "--explorer" in sys.argv,
        }
    )
)
