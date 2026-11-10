"""Bounded metadata and non-pickle array artifacts; explicit integrity verification."""

import copy
import hashlib
import io
import json
import os
import stat
from pathlib import Path
from typing import Any

import numpy as np

from soma.core.provenance import sha256
from soma.pipeline.derivatives import private_output
from soma.results.contracts import SchemaError, canonical, seal, validate_result

MAX_METADATA = 2 * 1024**2
MAX_ARRAY = 64 * 1024**2
MAX_TOTAL = 256 * 1024**2


def _read(root: Path, relative: str, bound: int) -> bytes:
    rel = Path(relative)
    if (
        rel.is_absolute()
        or not rel.parts
        or "\\" in relative
        or ":" in relative
        or any(x in {"..", "."} for x in rel.parts)
    ):
        raise SchemaError("Unsafe artifact reference")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory = os.open(root.resolve(), flags | os.O_DIRECTORY)
    try:
        for component in rel.parts[:-1]:
            nxt = os.open(component, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = nxt
        descriptor = os.open(rel.parts[-1], flags | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > bound:
                raise SchemaError("Artifact file exceeds bound or is not regular")
            data = stream.read(bound + 1)
            if len(data) > bound:
                raise SchemaError("Artifact file grew beyond bound")
            return data
    except OSError as error:
        raise SchemaError("Missing or symlinked artifact file") from error
    finally:
        os.close(directory)


def read_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise SchemaError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(token: str) -> None:
        raise SchemaError("Nonfinite JSON constant: " + token)

    try:
        value = json.loads(
            _read(path.parent, path.name, MAX_METADATA),
            object_pairs_hook=pairs,
            parse_constant=invalid,
        )
    except (ValueError, RecursionError) as error:
        raise SchemaError("Invalid bounded JSON metadata") from error
    if not isinstance(value, dict):
        raise SchemaError("Metadata object required")
    return value


def inspect_result(path: Path) -> dict[str, Any]:
    """Validate bounded metadata only; never read/hash/materialize numerical files."""
    value = read_json(path)
    status = validate_result(value)
    return {"envelope": value, "validation": status, "integrity": "NOT_CHECKED"}


def _load(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    value = inspect_result(path)["envelope"]
    arrays: dict[str, Any] = {}
    total = 0
    for name, descriptor in value["payload"]["arrays"].items():
        raw = _read(path.parent, descriptor["file"], MAX_ARRAY)
        total += len(raw)
        if total > MAX_TOTAL:
            raise SchemaError("Total artifact payload exceeds bound")
        if value["checksums"]["arrays"].get(name) != hashlib.sha256(raw).hexdigest():
            raise SchemaError("Array file checksum mismatch")
        try:
            stream = io.BytesIO(raw)
            version = np.lib.format.read_magic(stream)
            if version == (1, 0):
                shape, _, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=16384)
            elif version == (2, 0):
                shape, _, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=16384)
            else:
                raise SchemaError("Unsupported NPY version")
            count = 1
            for n in shape:
                count *= int(n)
            if (
                dtype.kind not in "biuf"
                or count * dtype.itemsize > MAX_ARRAY
                or stream.tell() + count * dtype.itemsize != len(raw)
            ):
                raise SchemaError("Invalid NPY allocation/dtype/length")
            arrays[name] = np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=16384)
            arrays[name].flags.writeable = False
        except (ValueError, EOFError, OSError) as error:
            raise SchemaError("Corrupt or unsupported numerical file") from error
    validate_result(value, arrays)
    status = {
        "integrity": "VERIFIED",
        "arrays": len(arrays),
        "payload_bytes": total,
        "metadata_sha256": value["checksums"]["metadata"],
        "authentication": "NOT_PROVIDED_BY_CHECKSUMS",
    }
    return value, arrays, status


def verify_integrity(path: Path) -> dict[str, Any]:
    """Read/hash bounded byte snapshots and validate headers/values, not just names."""
    return _load(path)[2]


def load_result(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verified metadata and read-only arrays from the same bounded byte snapshots."""
    value, arrays, _ = _load(path)
    return value, arrays


def save_result(value: dict[str, Any], arrays: dict[str, Any], directory: Path) -> Path:
    """Exclusive new artifact directory; JSON is published last; never overwrite."""
    validate_result(value, arrays)
    private_output(directory)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = copy.deepcopy(value)
    (directory / "arrays").mkdir(mode=0o700)
    for name, descriptor in output["payload"]["arrays"].items():
        p = directory / descriptor["file"]
        if np.asarray(arrays[name]).nbytes > MAX_ARRAY:
            raise SchemaError("Array exceeds size bound")
        with p.open("xb") as stream:
            np.save(stream, np.asarray(arrays[name]), allow_pickle=False)
        output["checksums"]["arrays"][name] = sha256(p)
    output = seal(output)
    data = canonical(output)
    if len(data) + 1 > MAX_METADATA:
        raise SchemaError("Metadata exceeds size bound")
    path = directory / "result.json"
    with path.open("xb") as stream:
        stream.write(data + b"\n")
    verify_integrity(path)
    return path


def verify_provenance(path: Path, *, input_root: Path | None = None) -> dict[str, Any]:
    """Verify artifact and explicit relative manifest inputs; no private-path inference."""
    status = verify_integrity(path)
    value = read_json(path)
    inputs = value["payload"]["domain"].get("inputs", {})
    if value["result_kind"] != "experiment.manifest":
        return {**status, "input_identity": "INDETERMINATE: no recorded manifest input hashes"}
    if not inputs:
        return {
            **status,
            "input_identity": "NOT_APPLICABLE: no external input files declared",
            "logical_dataset_identity": value.get("dataset_identity", "UNRECORDED"),
        }
    if input_root is None:
        return {**status, "input_identity": "INDETERMINATE: explicit input_root required"}
    for relative, expected in inputs.items():
        if hashlib.sha256(_read(input_root, relative, MAX_ARRAY)).hexdigest() != expected:
            raise SchemaError("Input checksum mismatch")
    return {
        **status,
        "input_identity": "VERIFIED",
        "input_files": len(inputs),
        "scientific_validity": "NOT_ESTABLISHED",
    }
