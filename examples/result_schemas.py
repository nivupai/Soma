"""Eight versioned-result workflows, deterministic synthetic data only.

Run python -m examples.result_schemas. No historical source is overwritten.
"""

import copy
import json
import tempfile
from pathlib import Path

import numpy as np

from soma.sdk.eeg import Signal, WelchConfig, welch
from soma.sdk.imaging import Volume
from soma.sdk.results import (
    SchemaError,
    compare_results,
    create_result,
    load_result,
    migrate_legacy,
    save_result,
    validate_result,
    verify_integrity,
)


def spectrum():
    signal = Signal(4e-6 * np.sin(2 * np.pi * 10 * np.arange(1600) / 160), 160)
    spec = welch(signal, WelchConfig())
    arrays = {"frequencies": spec.frequencies, "density": spec.density[None, :]}
    domain = {
        "fs_hz": 160.0,
        "channels": ["synthetic-Cz"],
        "reference": None,
        "window": {"duration_s": 10.0, "nperseg": 320, "noverlap": 160},
        "psd_config": {
            k: spec.metadata[k]
            for k in ["nperseg", "noverlap", "window", "average", "scaling", "sidedness"]
        },
        "task": "synthetic sinusoid",
    }
    result = create_result(
        "eeg.spectrum",
        domain,
        arrays=arrays,
        provenance={"source": "deterministic synthetic sine", "seed": None},
        method={"id": "NeuroDSP.Welch", "version": "density-v1"},
        parameters={"nperseg": 320, "noverlap": 160},
        units={"density": "V^2/Hz", "frequency": "Hz"},
        dataset_identity="synthetic-10Hz-4uV",
        subject_identity=None,
        statistical_estimand="one-sided spectral power density",
        spatial_reference=None,
        temporal_reference={"fs_hz": 160.0, "time_origin_s": 0.0},
    )
    return result, arrays


def geometry(frame="RAS"):
    volume = Volume(np.zeros((4, 5, 6)), np.diag([0.002, 0.003, 0.004, 1.0]))
    domain = {
        "image_identity": "synthetic-grid-v1",
        "shape": list(volume.shape),
        "affine": volume.affine_m.tolist(),
        "spacing": volume.spacing_m.tolist(),
        "grid_identity": volume.grid_id,
    }
    return create_result(
        "mri.geometry",
        domain,
        provenance={"source": "synthetic grid"},
        method={"id": "affine-inspection", "version": "1"},
        parameters={},
        units={"length": "m"},
        dataset_identity="synthetic-grid",
        subject_identity=None,
        spatial_reference={
            "frame": frame,
            "space": "synthetic",
            "unit": "m",
            "grid_identity": volume.grid_id,
        },
        temporal_reference=None,
        statistical_estimand=None,
    )


def segmentation():
    domain = {
        "image_identity": "synthetic-sphere",
        "grid_identity": "analytic-grid",
        "ontology": {"1": "sphere"},
        "label_correspondence": {"1": "1"},
        "boundary_definition": "area-weighted exposed voxel-face centers",
    }
    return create_result(
        "mri.segmentation",
        domain,
        values={"Dice": 0.9, "ASSD_mm": 1.0},
        provenance={"source": "synthetic reference/prediction demonstration"},
        method={"id": "physical-surfel-score", "version": "1"},
        parameters={"mask": "whole-grid"},
        units={"overlap": "1", "distance": "mm", "volume": "mm^3"},
        dataset_identity="synthetic-sphere",
        subject_identity=None,
        spatial_reference={"frame": "RAS", "space": "synthetic", "unit": "mm"},
        temporal_reference=None,
        statistical_estimand="per-label overlap and boundary distance",
    )


def run():
    eeg, arrays = spectrum()
    mri = geometry()
    seg = segmentation()
    validate_result(eeg, arrays)
    validate_result(mri)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = save_result(eeg, arrays, root / "artifact")
        loaded, data = load_result(path)
        np.testing.assert_array_equal(data["density"], arrays["density"])
        integrity = verify_integrity(path)
        legacy = root / "legacy.json"
        legacy.write_text(
            '{"schema_version":1,"source":{"dataset":"synthetic"},"parameters":{"fs_hz":160}}'
        )
        migrated, _, receipt = migrate_legacy(legacy, source_format="core-manifest-v1")
        assert migrated["payload"]["values"] == json.loads(legacy.read_text())
        different = geometry("LPS")
        comparison = compare_results(mri, different)
        invalid = copy.deepcopy(eeg)
        invalid["schema_version"] = "99.0.0"
        try:
            validate_result(invalid)
        except SchemaError:
            rejected = True
        else:
            raise AssertionError("Future schema unexpectedly accepted")
        from fastapi.testclient import TestClient

        from services.explorer_api.app import create_app
        from services.explorer_api.registry import Configuration, Entry, Registry

        entry = Entry(
            id="versioned-demo",
            kind="experiment",
            label="Versioned synthetic PSD",
            root="artifacts",
            file="artifact/result.json",
            synthetic=True,
        )
        registry = Registry(Configuration(roots={"artifacts": str(root)}, entries=[entry]))
        with TestClient(create_app(registry), base_url="http://127.0.0.1") as client:
            response = client.get("/api/experiments")
            assert response.status_code == 200
            versioned = next(a for a in response.json() if a["id"] == "versioned-demo")
            assert versioned["schema_version"] == "1.1.0"
        return {
            "EEG_schema": loaded["schema_version"],
            "MRI_kind": mri["result_kind"],
            "coordinate_mismatch": comparison["status"],
            "segmentation_comparison": compare_results(seg, seg)["status"],
            "migration": receipt["state"],
            "future_schema_rejected": rejected,
            "checksum": integrity["integrity"],
            "Explorer_schema": versioned["schema_version"],
        }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
