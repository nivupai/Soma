"""Public import, metadata and boundary regressions; existing scientific tests unchanged."""

import importlib
import json
import subprocess
import sys
from dataclasses import replace
from importlib.metadata import version

import numpy as np
import pytest
from fastapi.testclient import TestClient

from soma import __version__
from soma.sdk.eeg import Signal, WelchConfig, eeg_spectrum, welch
from soma.sdk.imaging import (
    Frame,
    Points,
    Transform,
    Volume,
    require_same_space,
    resample_labels,
    score,
)
from soma.sdk.provenance import (
    array_fingerprint,
    read_manifest,
    require_comparable,
    result_metadata,
)


@pytest.mark.parametrize(
    "name", ["imaging", "eeg", "fmri", "source", "provenance", "synthetic", "explorer"]
)
def test_public_import(name):
    importlib.import_module("soma.sdk." + name)


def test_lightweight_root_and_version():
    assert version("soma-neuro") == __version__
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import soma.sdk; assert 'mne' not in sys.modules; "
                "assert 'nilearn' not in sys.modules"
            ),
        ],
        check=True,
    )


def test_exports_preserve_implementation_identity():
    from soma.imaging.nifti import load_nifti
    from soma.sdk import imaging
    from soma.signal.spectral import welch as original

    assert imaging.load_nifti is load_nifti and welch is original


def test_units_and_psd_oracle():
    time = np.arange(1600) / 160
    signal = Signal(2e-6 * np.sin(2 * np.pi * 10 * time), 160)
    result = eeg_spectrum(signal, WelchConfig())
    assert result.peak_frequency == 10
    assert np.isclose(result.band_power(8, 13), 2e-12, rtol=1e-10, atol=0)
    with pytest.raises(ValueError, match="volts"):
        eeg_spectrum(replace(signal, unit="uV"))


def test_space_contracts_and_label_resampling():
    a = np.diag([0.002, 0.002, 0.002, 1.0])
    volume = Volume(
        np.ones((3, 3, 3), np.uint8), a, "labels", {"subject": "synthetic", "space": "native"}
    )
    require_same_space(volume, volume, subject="synthetic", space="native")
    with pytest.raises(ValueError, match="subject/space"):
        require_same_space(
            volume, replace(volume, metadata={}), subject="synthetic", space="native"
        )
    shifted = a.copy()
    shifted[0, 3] = 0.002
    with pytest.raises(ValueError, match="grids"):
        require_same_space(
            volume, replace(volume, affine_m=shifted), subject="synthetic", space="native"
        )
    out = resample_labels(
        volume, volume, reference_to_source=Transform(Frame.RAS, Frame.RAS, np.eye(4))
    )
    np.testing.assert_array_equal(out.array(), volume.array())
    with pytest.raises(ValueError, match="RAS"):
        resample_labels(
            volume, volume, reference_to_source=Transform(Frame.HEAD, Frame.HEAD, np.eye(4))
        )
    with pytest.raises(ValueError, match="metres"):
        Points(np.zeros((1, 3)), Frame.RAS, "mm")


def test_segmentation_ontology_and_independent_predictions():
    from examples.segmentation import inputs

    p, r = inputs()
    report = score(p, r)
    row = report["labels"][0]
    assert 0 < row["Dice"] < 1 and row["HD95_mm"] > 0
    assert p.provenance["truth_used"] is False
    with pytest.raises(ValueError, match="interpretation"):
        score(p, replace(r, ontology={1: "other tissue"}))
    with pytest.raises(ValueError, match="Unknown segmentation"):
        score(
            replace(
                p, volume=Volume(np.full(p.volume.shape, 2, np.uint8), p.volume.affine_m, "labels")
            ),
            r,
        )
    with pytest.raises(ValueError, match="Subject/world"):
        score(p, replace(r, subject="other"))


def metadata(**changes):
    kwargs = dict(
        input_fingerprint=array_fingerprint(np.arange(5.0)),
        method="test-v1",
        parameters={"ontology": {1: "sphere"}},
        units="mm",
        data_identity="synthetic",
        estimand="boundary distance",
        spatial_reference="synthetic-RAS",
        interpretation="synthetic",
        warnings=[],
        source={"synthetic": True},
    )
    kwargs.update(changes)
    return result_metadata(**kwargs)


def test_result_metadata_roundtrip(tmp_path):
    result = metadata()
    assert result["application_version"] == version("soma-neuro")
    assert result["confirmatory_claim_allowed"] is False
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(result))
    assert read_manifest(path) == result
    require_comparable(result, read_manifest(path))
    for key in [
        "input_fingerprint",
        "method",
        "parameters",
        "units",
        "data_identity",
        "estimand",
        "spatial_reference",
        "interpretation",
        "source",
        "warnings",
    ]:
        assert key in result


@pytest.mark.parametrize(
    "field,value",
    [
        ("units", "m"),
        ("spatial_reference", "LPS"),
        ("parameters", {"ontology": {1: "other"}}),
        ("estimand", "other contrast"),
        ("data_identity", "other subject"),
    ],
)
def test_incompatible_results_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        require_comparable(metadata(), metadata(**{field: value}))


@pytest.mark.parametrize(
    "changes",
    [
        {"input_fingerprint": "unknown"},
        {"units": ""},
        {"interpretation": "confirmatory"},
        {"parameters": {"bad": float("nan")}},
    ],
)
def test_metadata_rejects_invalid(changes):
    with pytest.raises(ValueError):
        metadata(**changes)


def test_fingerprint_tracks_shape_dtype_and_content():
    a = np.arange(6, dtype=np.float64)
    assert array_fingerprint(a) == array_fingerprint(a.copy())
    assert (
        len(
            {
                array_fingerprint(a),
                array_fingerprint(a.reshape(2, 3)),
                array_fingerprint(a.astype(np.float32)),
                array_fingerprint(a + 1),
            }
        )
        == 4
    )
    with pytest.raises(ValueError):
        array_fingerprint([np.nan])


def test_manifest_rejects_nonfinite_and_nondict(tmp_path):
    path = tmp_path / "bad.json"
    for text in ["[]", '{"bad":NaN}']:
        path.write_text(text)
        with pytest.raises(ValueError):
            read_manifest(path)


def test_sdk_fmri_cannot_bypass_human_policy():
    from soma.sdk.fmri import InferencePolicy, ModelConfig, build_design
    from soma.sdk.synthetic import simulate_fmri

    run, _ = simulate_fmri(seed=16042)
    config = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    design, _ = build_design(run, config)
    human = replace(
        run,
        subject="human",
        preprocessing="validated",
        provenance={"source": "test fixture", "preprocessing_evidence": "fixture only"},
    )
    assert not InferencePolicy().evaluate(human, config, design)["confirmatory_claim_allowed"]
    with pytest.raises(ValueError, match="Unsupported confirmatory"):
        InferencePolicy(mode="confirmatory").evaluate(human, config, design)


def test_optional_explorer_failure(monkeypatch):
    import soma.sdk.explorer as explorer

    monkeypatch.setattr(explorer, "find_spec", lambda name: None)
    with pytest.raises(ImportError, match=r"soma-neuro\[explorer\]"):
        explorer.create_app()


def test_explorer_sdk_science_and_sanitized_export(tmp_path, monkeypatch):
    monkeypatch.delenv("SOMA_EXPLORER_CONFIG", raising=False)
    from soma.sdk.explorer import create_app

    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        for path in [
            "/api/catalog",
            "/api/eeg/demo-eeg/analysis",
            "/api/volumes/demo-mri",
            "/api/fmri/demo-fmri",
            "/api/experiments/demo-calibration/export?format=json",
        ]:
            r = client.get(path)
            assert r.status_code == 200
            assert "/Users/" not in r.text
        assert client.get("/api/volumes/..%2F..%2Fetc%2Fpasswd").status_code in {400, 404, 422}


@pytest.mark.parametrize(
    "name",
    [
        "mri_geometry",
        "segmentation",
        "surface_qc",
        "eeg_analysis",
        "source_diagnostics",
        "fmri_contrast",
        "provenance",
        "explorer",
    ],
)
def test_executable_examples(name, monkeypatch):
    monkeypatch.delenv("SOMA_EXPLORER_CONFIG", raising=False)
    result = importlib.import_module("examples." + name).run()
    assert isinstance(result, dict) and result
    json.dumps(result, allow_nan=False)


def test_packaged_calibration_preserves_historical_values():
    import hashlib
    from importlib.resources import files
    from pathlib import Path

    original = Path("experiments/milestone141/verification.json").read_bytes()
    historical = json.loads(original)
    excerpt = json.loads(files("soma.resources").joinpath("calibration-demo.json").read_text())
    assert excerpt["source_receipt_sha256"] == hashlib.sha256(original).hexdigest()
    assert excerpt["protocol_sha256"] == historical["protocol_sha256"]
    for row in excerpt["calibration"]:
        assert row in historical["calibration"]
        assert row["case"] == "spatial-iid-independent-m343" and row["model"] == "ols"


def test_packaged_protocol_documents_match_source():
    import hashlib
    from importlib.resources import files
    from pathlib import Path

    from soma.resources import protocol_document_sha256

    for name in ["REPLICATION_PROTOCOL.md", "DECODING_PROTOCOL.md"]:
        content = Path("docs", name).read_bytes()
        assert files("soma.resources").joinpath(name).read_bytes() == content
        assert protocol_document_sha256(name) == hashlib.sha256(content).hexdigest()


def test_output_privacy_uses_destination_repository(tmp_path):
    import subprocess

    from soma.datasets.human_mri import safe_local_output
    from soma.pipeline.derivatives import private_output

    repo = tmp_path / "other-repository"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / ".gitignore").write_text("reports/\ndata/derived/\nderivatives/\n")
    for guard in [safe_local_output, private_output]:
        with pytest.raises(ValueError, match="ignored"):
            guard(repo / "docs/private-image")
        guard(repo / "reports/permitted")
    private_output(repo / "derivatives/permitted")
    with pytest.raises(ValueError):
        safe_local_output(repo / "derivatives/stricter-human-policy")


def test_source_archive_privacy_without_git(tmp_path):
    from soma.core.paths import output_repository
    from soma.pipeline.derivatives import private_output

    root = tmp_path / "source-archive"
    (root / "src/soma").mkdir(parents=True)
    (root / "src/soma/__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "soma-neuro"\n')
    assert output_repository(root / "docs/private") == root
    with pytest.raises(ValueError, match="ignored"):
        private_output(root / "docs/private")
