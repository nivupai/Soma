"""Explicit read-only legacy adapters; no bulk discovery or scientific inference."""

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from soma import __version__
from soma.core.provenance import sha256
from soma.results.contracts import SchemaError, canonical, create_result, seal
from soma.results.io import MAX_ARRAY, read_json

FORMATS = {
    "core-manifest-v1",
    "sdk-metadata-v1",
    "milestone-verification-json",
    "welch-manifest-v1",
}


def migrate_legacy(
    path: Path, *, source_format: str, channel: str | None = None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read one explicitly selected legacy source. Never follow stored absolute paths.

    Generic records remain INDETERMINATE; their entire original JSON/provenance is
    preserved, not reconstructed. Welch migration requires recorded axes/config
    and an explicit channel from a bounded adjacent synthetic spectra.npz archive.
    """
    if source_format not in FORMATS:
        raise SchemaError("Unsupported legacy adapter; select an explicit reviewed format")
    original = read_json(path)
    source_hash = sha256(path)
    arrays: dict[str, Any] = {}
    if (
        source_format in {"core-manifest-v1", "welch-manifest-v1"}
        and original.get("schema_version") != 1
    ):
        raise SchemaError("Not a core manifest v1")
    if source_format == "sdk-metadata-v1" and original.get("sdk_schema_version") != 1:
        raise SchemaError("Not SDK metadata v1")
    if source_format == "welch-manifest-v1":
        if original.get("source", {}).get("dataset") != "synthetic":
            raise SchemaError("Welch adapter is bounded to explicitly synthetic recordings")
        params = original.get("parameters", {})
        config = params.get("spectra", {}).get(channel, {})
        required = {
            "fs_hz",
            "units",
            "nperseg",
            "noverlap",
            "window",
            "average",
            "scaling",
            "sidedness",
        }
        if not required <= config.keys() or channel not in params.get("selected_channels", []):
            raise SchemaError("Missing recorded PSD metadata or explicit channel")
        archive = path.parent / "spectra.npz"
        if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_ARRAY:
            raise SchemaError("Missing/unsafe legacy array archive")
        with zipfile.ZipFile(archive) as z:
            expected_names = {"frequencies.npy", "density.npy", "channels.npy"}
            if (
                len(z.infolist()) != 3
                or set(z.namelist()) != expected_names
                or sum(x.file_size for x in z.infolist()) > MAX_ARRAY
            ):
                raise SchemaError("Unexpected or excessive legacy archive")
            for member in z.infolist():
                with z.open(member) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version == (1, 0):
                        shape, _, dtype = np.lib.format.read_array_header_1_0(
                            stream, max_header_size=16384
                        )
                    elif version == (2, 0):
                        shape, _, dtype = np.lib.format.read_array_header_2_0(
                            stream, max_header_size=16384
                        )
                    else:
                        raise SchemaError("Unsupported legacy NPY header")
                    count = 1
                    for n in shape:
                        count *= int(n)
                    if (
                        dtype.kind not in "biufUS"
                        or count * dtype.itemsize > MAX_ARRAY
                        or stream.tell() + count * dtype.itemsize != member.file_size
                    ):
                        raise SchemaError("Invalid bounded legacy array allocation")
        with np.load(archive, allow_pickle=False, max_header_size=16384) as data:
            if set(data.files) != {"frequencies", "density", "channels"}:
                raise SchemaError("Unexpected legacy arrays")
            channels = data["channels"]
            if (
                channels.dtype.kind not in "US"
                or channels.ndim != 1
                or channels.tolist() != params["selected_channels"]
            ):
                raise SchemaError("Ambiguous channel identities")
            index = channels.tolist().index(channel)
            arrays = {
                "frequencies": data["frequencies"].copy(),
                "density": data["density"][[index]].copy(),
            }
        domain = {
            "fs_hz": config["fs_hz"],
            "channels": [channel],
            "window": {"nperseg": config["nperseg"], "noverlap": config["noverlap"]},
            "psd_config": {
                k: config[k]
                for k in ["nperseg", "noverlap", "window", "average", "scaling", "sidedness"]
            },
        }
        if "reference" in config:
            domain["reference"] = config["reference"]
        library_version = original.get("libraries", {}).get("neurodsp")
        if not library_version:
            raise SchemaError(
                "Numerical library identity unrecorded; "
                "use the core-manifest-v1 indeterminate adapter"
            )
        result = create_result(
            "eeg.spectrum",
            domain,
            arrays=arrays,
            interpretation_state="INDETERMINATE",
            provenance={"legacy_original": original, "observed_archive_sha256": sha256(archive)},
            method={
                "id": "NeuroDSP.Welch",
                "version": library_version,
            },
            parameters=params,
            units={"density": config["units"], "frequency": "Hz"},
            **(
                {"dataset_identity": original["source"]["file_identifier"]}
                if "file_identifier" in original["source"]
                else {}
            ),
            statistical_estimand="one-sided spectral power density",
            spatial_reference=None,
            temporal_reference={"fs_hz": config["fs_hz"]},
        )
        missing = [
            "reference montage",
            "task definition",
            "absolute time origin",
            "original array checksum",
        ]
    else:
        missing = ["complete domain-specific numerical contract"]
        result = create_result(
            "legacy.record",
            {"legacy_format": source_format, "missing_metadata": missing},
            values=original,
            interpretation_state="INDETERMINATE",
            provenance={"legacy_original": original},
        )
    receipt = {
        "source_format": source_format,
        "source_sha256": source_hash,
        "migration_software": "soma-neuro",
        "migration_version": __version__,
        "numerical_values_preserved": True,
        "original_JSON_sha256": hashlib.sha256(canonical(original)).hexdigest(),
        "missing_metadata": missing,
        "state": "INDETERMINATE",
        "source_modified": False,
        "selection": {"channel": channel} if source_format == "welch-manifest-v1" else None,
        "checksum_scope": "observed now; does not authenticate original execution",
    }
    result["migration"] = receipt
    if original.get("timestamp_utc") is not None:
        result["created_at"] = original["timestamp_utc"]
    result = seal(result)
    if sha256(path) != source_hash:
        raise SchemaError("Source changed during migration")
    return result, arrays, receipt
