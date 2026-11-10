"""Adversarial, numerical and semantic artifact regressions; no human datasets."""

import copy
import hashlib
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from examples.result_schemas import geometry, segmentation, spectrum
from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.cli import app
from soma.results.contracts import canonical, seal
from soma.sdk.results import (
    SchemaError,
    compare_results,
    convert_units,
    inspect_result,
    load_result,
    migrate_legacy,
    save_result,
    upgrade_schema,
    validate_result,
    verify_integrity,
    verify_provenance,
)


def test_roundtrip_metadata_inspection_never_reads_arrays(tmp_path, monkeypatch):
    result, arrays = spectrum()
    path = save_result(result, arrays, tmp_path / "artifact")
    target = path.parent / "arrays/density.npy"
    saved = target.read_bytes()
    target.unlink()
    assert inspect_result(path)["integrity"] == "NOT_CHECKED"
    with pytest.raises(SchemaError):
        load_result(path)
    target.write_bytes(saved)
    value, loaded = load_result(path)
    for key in arrays:
        np.testing.assert_array_equal(loaded[key], arrays[key])
    assert not loaded["density"].flags.writeable
    assert verify_integrity(path)["integrity"] == "VERIFIED"
    with pytest.raises(FileExistsError):
        save_result(value, dict(loaded), path.parent)


@pytest.mark.parametrize("version", ["2.0.0", "1.9.0", "01.0.0", "1.0", None, 1])
def test_unsupported_versions(version):
    value, _ = spectrum()
    value["schema_version"] = version
    with pytest.raises(SchemaError, match="Unsupported"):
        validate_result(value)


@pytest.mark.parametrize(
    "field", ["producer", "schema_version", "payload", "checksums", "method", "units"]
)
def test_missing_fields(field):
    value, _ = spectrum()
    del value[field]
    with pytest.raises(SchemaError):
        validate_result(value)


@pytest.mark.parametrize("place", ["envelope", "domain", "descriptor"])
def test_unknown_fields(place):
    value, _ = spectrum()
    target = (
        value
        if place == "envelope"
        else value["payload"]["domain"]
        if place == "domain"
        else value["payload"]["arrays"]["density"]
    )
    target["invented"] = 1
    with pytest.raises(SchemaError):
        validate_result(seal(value))


@pytest.mark.parametrize(
    "field,value",
    [
        ("units", {"density": "mm", "frequency": "Hz"}),
        ("units", {"density": "unknown", "frequency": "Hz"}),
        ("subject_identity", {}),
        ("method", {"id": "", "version": "1"}),
        ("created_at", "2026-11-09"),
        ("created_at", "not-a-time"),
        ("interpretation_state", "CLINICALLY_VALIDATED"),
    ],
)
def test_invalid_semantics(field, value):
    result, _ = spectrum()
    result[field] = value
    with pytest.raises(SchemaError):
        validate_result(seal(result))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_numerical_values(value):
    result, arrays = spectrum()
    arrays["density"][0, 0] = value
    with pytest.raises((SchemaError, ValueError)):
        validate_result(result, arrays)
    result, _ = spectrum()
    result["parameters"]["bad"] = value
    with pytest.raises(SchemaError):
        validate_result(result)


@pytest.mark.parametrize("mutation", ["shape", "dtype", "negative", "frequency", "allocation"])
def test_array_contracts(mutation):
    result, arrays = spectrum()
    if mutation == "shape":
        arrays["density"] = arrays["density"].T
    if mutation == "dtype":
        arrays["density"] = arrays["density"].astype(np.float32)
    if mutation == "negative":
        arrays["density"][0, 0] = -1
    if mutation == "frequency":
        arrays["frequencies"][1] = arrays["frequencies"][0]
    if mutation == "allocation":
        result["payload"]["arrays"]["density"]["shape"] = [2**40, 2**40]
        result = seal(result)
    with pytest.raises(SchemaError):
        validate_result(result, arrays)


def test_corruption_and_resealed_metadata_do_not_hide_array_changes(tmp_path):
    result, arrays = spectrum()
    path = save_result(result, arrays, tmp_path / "artifact")
    data = path.parent / "arrays/density.npy"
    raw = bytearray(data.read_bytes())
    raw[-1] ^= 1
    data.write_bytes(raw)
    with pytest.raises(SchemaError, match="checksum"):
        load_result(path)
    value = json.loads(path.read_text())
    value["checksums"]["arrays"]["density"] = hashlib.sha256(raw).hexdigest()
    path.write_bytes(canonical(seal(value)))
    with pytest.raises(SchemaError, match="fingerprint"):
        load_result(path)


@pytest.mark.parametrize(
    "reference",
    [
        "../secret.npy",
        "/etc/passwd",
        "arrays/../../outside.npy",
        "https://example.invalid/payload.npy",
    ],
)
def test_unsafe_references(reference):
    value, _ = spectrum()
    value["payload"]["arrays"]["density"]["file"] = reference
    with pytest.raises(SchemaError):
        validate_result(seal(value))


def test_symlink_escape_and_object_arrays(tmp_path):
    result, arrays = spectrum()
    path = save_result(result, arrays, tmp_path / "artifact")
    target = path.parent / "arrays/density.npy"
    outside = tmp_path / "outside.npy"
    target.rename(outside)
    target.symlink_to(outside)
    with pytest.raises(SchemaError):
        load_result(path)
    target.unlink()
    with target.open("wb") as stream:
        np.save(stream, np.array([object()], dtype=object), allow_pickle=True)
    value = json.loads(path.read_text())
    value["checksums"]["arrays"]["density"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_bytes(canonical(seal(value)))
    with pytest.raises(SchemaError):
        load_result(path)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', "[]"])
def test_malformed_json(tmp_path, text):
    p = tmp_path / "result.json"
    p.write_text(text)
    with pytest.raises(SchemaError):
        inspect_result(p)


def test_metadata_size_bound(tmp_path):
    p = tmp_path / "result.json"
    p.write_bytes(b" " * (2 * 1024**2 + 1))
    with pytest.raises(SchemaError):
        inspect_result(p)


def test_array_header_allocation_bound(tmp_path):
    result, arrays = spectrum()
    path = save_result(result, arrays, tmp_path / "artifact")
    target = path.parent / "arrays/density.npy"
    with target.open("wb") as stream:
        np.lib.format.write_array_header_1_0(
            stream, {"descr": "<f8", "fortran_order": False, "shape": (2**40, 2**40)}
        )
    value = json.loads(path.read_text())
    value["checksums"]["arrays"]["density"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_bytes(canonical(seal(value)))
    with pytest.raises(SchemaError):
        load_result(path)


def test_schema_upgrade_preserves_payload_and_provenance():
    old, _ = spectrum()
    old["schema_version"] = "1.0.0"
    old = seal(old)
    new = upgrade_schema(old)
    assert new["schema_version"] == "1.1.0" and old["schema_version"] == "1.0.0"
    assert new["payload"] == old["payload"] and new["provenance"] == old["provenance"]
    assert compare_results(old, new)["status"] == "COMPATIBLE"
    new["producer_version"] = "999.0.0"
    new = seal(new)
    assert compare_results(old, new)["compatible"]  # producer version is not a scientific estimand


@pytest.mark.parametrize(
    "field,value",
    [
        ("subject_identity", "another-person"),
        ("dataset_identity", "other"),
        ("statistical_estimand", "standardized effect"),
        ("method", {"id": "other estimator", "version": "1"}),
        ("method", {"id": "NeuroDSP.Welch", "version": "2"}),
        ("temporal_reference", {"fs_hz": 200}),
        ("parameters", {"nperseg": 640}),
    ],
)
def test_semantic_incompatibility(field, value):
    left, _ = spectrum()
    right = copy.deepcopy(left)
    right[field] = value
    right = seal(right)
    judgment = compare_results(left, right)
    assert judgment["status"] == "INCOMPATIBLE" and any(
        i["field"] == field for i in judgment["issues"]
    )


@pytest.mark.parametrize(
    "field,value", [("task", "motor execution"), ("reference", "different reference")]
)
def test_EEG_task_and_reference_mismatch(field, value):
    left, _ = spectrum()
    right = copy.deepcopy(left)
    right["payload"]["domain"][field] = value
    assert compare_results(left, seal(right))["status"] == "INCOMPATIBLE"


def test_coordinate_ontology_and_cross_modality_rejection():
    assert compare_results(geometry(), geometry("LPS"))["status"] == "INCOMPATIBLE"
    seg = segmentation()
    other = copy.deepcopy(seg)
    other["payload"]["domain"]["ontology"] = {"1": "different tissue"}
    assert compare_results(seg, seal(other))["status"] == "INCOMPATIBLE"
    eeg, _ = spectrum()
    assert compare_results(eeg, geometry())["status"] == "INCOMPATIBLE"
    other = copy.deepcopy(seg)
    other["spatial_reference"]["space"] = "template"
    assert compare_results(seg, seal(other))["status"] == "INCOMPATIBLE"


def test_unknown_is_not_inapplicable_and_units_are_explicit():
    value, arrays = spectrum()
    unknown = copy.deepcopy(value)
    del unknown["subject_identity"]
    assert compare_results(value, seal(unknown))["status"] == "INDETERMINATE"
    converted, data = convert_units(value, arrays, target="uV^2/Hz")
    assert compare_results(value, converted)["status"] == "CONVERTIBLE"
    np.testing.assert_allclose(data["density"], arrays["density"] * 1e12, rtol=1e-15, atol=0)
    np.testing.assert_array_equal(data["frequencies"], arrays["frequencies"])
    back, restored = convert_units(converted, data, target="V^2/Hz")
    np.testing.assert_allclose(restored["density"], arrays["density"], rtol=2e-15, atol=1e-30)
    with pytest.raises(SchemaError):
        convert_units(value, arrays, target="mm")
    with pytest.raises(SchemaError):
        convert_units(geometry(), {}, target="mm")


def test_generic_legacy_is_read_only_and_indeterminate(tmp_path):
    path = tmp_path / "legacy.json"
    raw = (
        b'{"schema_version":1,"parameters":{"number":1.23456789012345},'
        b'"source":{"dataset":"synthetic"}}'
    )
    path.write_bytes(raw)
    value, arrays, receipt = migrate_legacy(path, source_format="core-manifest-v1")
    assert path.read_bytes() == raw and value["payload"]["values"] == json.loads(raw)
    assert "created_at" not in value and "subject_identity" not in value
    assert (
        value["interpretation_state"] == "INDETERMINATE"
        and receipt["source_sha256"] == hashlib.sha256(raw).hexdigest()
    )
    assert compare_results(value, value)["status"] == "INDETERMINATE"
    assert arrays == {}


def test_recorded_welch_legacy_arrays_preserved(tmp_path):
    value, arrays = spectrum()
    domain = value["payload"]["domain"]
    cfg = {**domain["psd_config"], "fs_hz": 160.0, "units": "V^2/Hz"}
    original = {
        "schema_version": 1,
        "application_version": "0.1.0",
        "libraries": {"neurodsp": "2.3.0"},
        "source": {"dataset": "synthetic", "file_identifier": "portable-legacy-fixture"},
        "parameters": {"selected_channels": ["sine"], "spectra": {"sine": cfg}},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(original))
    np.savez(
        tmp_path / "spectra.npz",
        frequencies=arrays["frequencies"],
        density=arrays["density"],
        channels=np.array(["sine"]),
    )
    result, migrated, receipt = migrate_legacy(
        path, source_format="welch-manifest-v1", channel="sine"
    )
    for key in arrays:
        np.testing.assert_array_equal(migrated[key], arrays[key])
    assert (
        result["provenance"]["legacy_original"] == original
        and receipt["numerical_values_preserved"]
    )
    assert result["interpretation_state"] == "INDETERMINATE"
    with pytest.raises(SchemaError):
        migrate_legacy(path, source_format="welch-manifest-v1", channel="invented")


def test_manifest_input_hashes(tmp_path):
    from soma.sdk.results import create_result

    source = tmp_path / "inputs"
    source.mkdir()
    (source / "x.dat").write_bytes(b"synthetic")
    r = create_result(
        "experiment.manifest",
        {
            "computation": "identity",
            "inputs": {"x.dat": hashlib.sha256(b"synthetic").hexdigest()},
            "environment": {"python": "recorded"},
            "assumptions": [],
            "validation": {},
            "limitations": [],
        },
        provenance={},
        method={"id": "identity", "version": "1"},
        parameters={},
        units={},
    )
    path = save_result(r, {}, tmp_path / "artifact")
    assert "INDETERMINATE" in verify_provenance(path)["input_identity"]
    assert verify_provenance(path, input_root=source)["input_identity"] == "VERIFIED"
    (source / "x.dat").write_bytes(b"modified")
    with pytest.raises(SchemaError, match="Input checksum"):
        verify_provenance(path, input_root=source)


def test_cli_read_only_and_exclusive_migration(tmp_path):
    result, arrays = spectrum()
    path = save_result(result, arrays, tmp_path / "artifact")
    runner = CliRunner()
    for command in ["inspect", "validate", "verify-provenance"]:
        response = runner.invoke(app, ["results", command, str(path)])
        assert response.exit_code == 0, response.output
    assert runner.invoke(app, ["results", "compare", str(path), str(path)]).exit_code == 0
    legacy = tmp_path / "legacy.json"
    legacy.write_text('{"schema_version":1}')
    response = runner.invoke(
        app, ["results", "migrate", str(legacy), "--source-format", "core-manifest-v1"]
    )
    assert response.exit_code == 0 and json.loads(legacy.read_text()) == {"schema_version": 1}
    assert not (tmp_path / "result.json").exists()


def test_Explorer_integrity_future_versions_and_comparison(tmp_path):
    left, arrays = spectrum()
    p = save_result(left, arrays, tmp_path / "left")
    right = copy.deepcopy(left)
    right["subject_identity"] = "other"
    save_result(seal(right), arrays, tmp_path / "right")
    future = copy.deepcopy(left)
    future["schema_version"] = "99.0.0"
    (tmp_path / "future.json").write_bytes(canonical(seal(future)))
    entries = [
        Entry(id=n, kind="experiment", label=n, root="artifacts", file=f, synthetic=True)
        for n, f in [
            ("left", "left/result.json"),
            ("right", "right/result.json"),
            ("future", "future.json"),
        ]
    ]
    with TestClient(
        create_app(Registry(Configuration(roots={"artifacts": str(tmp_path)}, entries=entries))),
        base_url="http://127.0.0.1",
    ) as c:
        results = {a["id"]: a for a in c.get("/api/experiments").json()}
        assert results["left"]["validation_status"] == "FORMAT_AND_INTEGRITY_VERIFIED"
        assert (
            results["future"]["validation_status"] == "UNSUPPORTED_VERSION"
            and not results["future"]["figures"]
        )
        assert c.get("/api/experiments/future/export").status_code == 422
        response = c.post("/api/experiments/compare", json={"ids": ["left", "right"]})
        assert response.status_code == 409
        target = p.parent / "arrays/density.npy"
        target.write_bytes(b"corrupt")
        results = {a["id"]: a for a in c.get("/api/experiments").json()}
        assert results["left"]["state"] == "INVALID"


def test_numerical_reproducibility_suite():
    from soma.results.reproducibility import run_suite

    result = run_suite()
    assert result["all_passed"] and len(result["cases"]) == 12
    assert all(
        c["max_absolute_error"] <= c["atol"] + c["rtol"] * c["reference_scale"]
        for c in result["cases"]
    )


def test_eight_result_examples():
    from examples.result_schemas import run

    result = run()
    assert len(result) == 8


def domain_result(kind):
    from soma.sdk.results import create_result

    spatial = {"frame": "RAS", "space": "synthetic", "unit": "m"}
    common = dict(
        provenance={"source": "explicit synthetic fixture"},
        method={"id": "fixture", "version": "1"},
        parameters={},
        dataset_identity="synthetic",
        subject_identity="synthetic",
        statistical_estimand="declared fixture quantity",
        spatial_reference=spatial,
        temporal_reference=None,
    )
    if kind == "source.reconstruction":
        domain = dict(
            source_space_identity="sources-v1",
            forward_identity="forward-sha",
            inverse_identity="inverse-sha",
            regularization={"lambda2": 0.1},
            conductivity_S_m=[0.3, 0.006, 0.3],
            anatomical_readiness="INDETERMINATE",
            resolution_definition="linear PSF",
        )
        arrays = {"amplitudes": np.zeros((3, 10))}
        units = {"amplitude": "A*m", "length": "m"}
    elif kind == "mri.registration":
        domain = dict(
            fixed_identity="fixed",
            moving_identity="moving",
            transform_direction="reference_to_source",
            frame="RAS",
        )
        arrays = {"transform": np.eye(4)}
        units = {"length": "m"}
    elif kind == "mri.surface":
        domain = dict(
            geometry_identity="tetra", frame="RAS", surface_semantics="oriented triangular boundary"
        )
        arrays = {}
        units = {"length": "m", "area": "m^2", "volume": "m^3"}
    elif kind.startswith("fmri."):
        domain = dict(
            session="1",
            task="synthetic",
            run="1",
            tr_s=2.0,
            design_identity="fixed-design-sha",
            contrast={"task": 1.0},
            noise_model="ols",
            inference_policy={"confirmatory_claim_allowed": False, "mode": "descriptive"},
            correction="bh",
            preprocessing={"status": "synthetic", "source": "known generator"},
        )
        arrays = {}
        units = {"effect": "BOLD/regressor", "variance": "(BOLD/regressor)^2", "statistic": "1"}
        if kind == "fmri.roi":
            domain.update(roi_ontology={"1": "analytic region"}, roi_space="synthetic")
            units = {"effect": "BOLD/regressor"}
        common["interpretation_state"] = "DESCRIPTIVE_ONLY"
    elif kind == "eeg.bursts":
        domain = dict(
            fs_hz=160.0,
            channels=["Cz"],
            reference="average",
            window={"start_s": 0.0, "stop_s": 1.0},
            thresholds={
                "low": 2e-6,
                "high": 4e-6,
                "minimum_duration_s": 0.3,
                "calibration": "independent rest",
                "filter": "explicit bandpass",
            },
            interval_convention="half-open seconds",
        )
        arrays = {"intervals": np.array([[0.1, 0.5]])}
        units = {"amplitude": "V", "time": "s"}
        common["spatial_reference"] = None
    elif kind == "eeg.time_frequency":
        domain = dict(
            fs_hz=160.0,
            channels=["Cz"],
            reference="average",
            window={"start_s": 0.0, "stop_s": 1.0},
            tf_config={
                "frequencies_hz": [10.0, 20.0],
                "n_cycles": 5.0,
                "power_definition": "Morlet squared modulus",
            },
        )
        arrays = {
            "frequencies": np.array([10.0, 20.0]),
            "times": np.arange(10) / 160,
            "power": np.ones((2, 1, 2, 10)),
            "valid": np.ones((2, 10), bool),
        }
        units = {"power": "V^2", "frequency": "Hz", "time": "s"}
        common["spatial_reference"] = None
    else:
        raise AssertionError(kind)
    return create_result(kind, domain, arrays=arrays, units=units, **common), arrays


@pytest.mark.parametrize(
    "kind",
    [
        "eeg.time_frequency",
        "eeg.bursts",
        "mri.surface",
        "mri.registration",
        "source.reconstruction",
        "fmri.contrast",
        "fmri.roi",
    ],
)
def test_supported_domain_families(kind, tmp_path):
    result, arrays = domain_result(kind)
    validate_result(result, arrays)
    path = save_result(result, arrays, tmp_path / "result")
    assert load_result(path)[0]["result_kind"] == kind


@pytest.mark.parametrize(
    "field,value",
    [
        ("noise_model", "ar3"),
        ("inference_policy", {"confirmatory_claim_allowed": True}),
        ("tr_s", -1),
        ("contrast", {}),
    ],
)
def test_invalid_fmri_contracts(field, value):
    result, arrays = domain_result("fmri.contrast")
    result["payload"]["domain"][field] = value
    with pytest.raises(SchemaError):
        validate_result(seal(result), arrays)


@pytest.mark.parametrize(
    "field,value",
    [
        ("noise_model", "ar1"),
        ("correction", "bonferroni"),
        ("contrast", {"other": 1.0}),
        ("preprocessing", {"status": "different"}),
    ],
)
def test_fmri_assumptions_not_automatically_comparable(field, value):
    a, _ = domain_result("fmri.contrast")
    b = copy.deepcopy(a)
    b["payload"]["domain"][field] = value
    assert compare_results(a, seal(b))["status"] == "INCOMPATIBLE"


def test_tf_axes_burst_thresholds_and_source_readiness():
    result, arrays = domain_result("eeg.time_frequency")
    arrays["valid"] = np.ones((3, 10), bool)
    with pytest.raises(SchemaError):
        validate_result(result, arrays)
    result, arrays = domain_result("eeg.bursts")
    result["payload"]["domain"]["thresholds"]["low"] = 9
    with pytest.raises(SchemaError):
        validate_result(seal(result), arrays)
    result, arrays = domain_result("source.reconstruction")
    result["payload"]["domain"]["anatomical_readiness"] = "CLINICALLY_VALIDATED"
    with pytest.raises(SchemaError):
        validate_result(seal(result), arrays)


def test_existing_sdk_comparison_dispatches_versioned_results():
    from soma.sdk.provenance import require_comparable

    value, _ = spectrum()
    require_comparable(value, value)
    different = copy.deepcopy(value)
    different["statistical_estimand"] = "different quantity"
    with pytest.raises(SchemaError):
        require_comparable(value, seal(different))


def test_versioned_subject_identity_redacted_without_source_mutation(tmp_path):
    result, arrays = spectrum()
    result["subject_identity"] = "synthetic-private-identity"
    path = save_result(seal(result), arrays, tmp_path / "artifact")
    raw = path.read_bytes()
    entry = Entry(
        id="versioned",
        kind="experiment",
        label="versioned",
        root="fixture",
        file="artifact/result.json",
        synthetic=True,
    )
    with TestClient(
        create_app(Registry(Configuration(roots={"fixture": str(tmp_path)}, entries=[entry]))),
        base_url="http://127.0.0.1",
    ) as c:
        response = c.get("/api/experiments/versioned/export")
        assert response.status_code == 200 and "synthetic-private-identity" not in response.text
    assert path.read_bytes() == raw
