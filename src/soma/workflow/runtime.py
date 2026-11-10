"""Verified serial extension of Soma's existing cache and stage abstractions."""

import fcntl
import hashlib
import inspect
import json
import os
import platform
import shutil
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import distribution, version
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from threadpoolctl import threadpool_info, threadpool_limits

from soma import __version__
from soma.pipeline.cache import decode, encode, source_hash
from soma.results.compatibility import compare_results
from soma.results.contracts import canonical, create_result
from soma.results.io import load_result, read_json, save_result
from soma.simulations.calibration import atomic_json
from soma.workflow.model import (
    Artifact,
    Graph,
    Stage,
    WorkflowError,
    digest,
    invalidation,
    relative,
)

KEY_ALGORITHM = "soma.workflow.sha256.typed-v1"
Fault = Callable[[str, str], None]
_SCIENCE_LOCK = threading.RLock()


@dataclass(frozen=True)
class Operation:
    name: str
    inputs: dict[str, str]
    outputs: dict[str, str]
    calculate: Callable[[dict[str, Any], dict[str, Any], int | None], dict[str, Any]]
    algorithm_version: str = "1"
    stochastic: bool = False


class Registry:
    """Code-owned allowlist; workflow descriptions never resolve imports or commands."""

    def __init__(self, operations: list[Operation]) -> None:
        self.operations = {op.name: op for op in operations}
        if len(self.operations) != len(operations):
            raise WorkflowError("Duplicate registered implementation")
        if any(getattr(op.calculate, "__closure__", None) for op in operations):
            raise WorkflowError("Registered operations cannot capture undeclared closure state")
        self.source = source_hash()

    def validate(self, graph: Graph) -> list[Stage]:
        order = graph.order()
        artifacts = {a.id: a for a in graph.artifacts}
        for stage in order:
            for port in [*stage.inputs, *stage.outputs]:
                from soma.workflow.model import identifier

                identifier(port)
            op = self.operations.get(stage.implementation)
            if op is None or stage.algorithm_version != op.algorithm_version:
                raise WorkflowError("Unregistered implementation or incompatible algorithm version")
            if set(stage.inputs) != set(op.inputs) or set(stage.outputs) != set(op.outputs):
                raise WorkflowError("Registered port contract mismatch")
            for ports, types in [(stage.inputs, op.inputs), (stage.outputs, op.outputs)]:
                if any(artifacts[node].kind != types[port] for port, node in ports.items()):
                    raise WorkflowError("Incompatible artifact type")
            spatial = [
                artifacts[n].metadata["spatial_reference"]
                for n in [*stage.inputs.values(), *stage.outputs.values()]
                if artifacts[n].metadata["spatial_reference"] is not None
            ]
            if spatial and any(x.get("frame") != "RAS" or x.get("unit") != "m" for x in spatial):
                raise WorkflowError("Registered spatial operations require RAS metres")
            if spatial and any(x != spatial[0] for x in spatial):
                raise WorkflowError("Coordinate mismatch; no implicit transform stage registered")
            connected = [
                artifacts[n].metadata for n in [*stage.inputs.values(), *stage.outputs.values()]
            ]
            for field in ["dataset_identity", "subject_identity"]:
                if connected and any(m[field] != connected[0][field] for m in connected):
                    raise WorkflowError("Dataset/subject mismatch across computation ports")
            for node in [*stage.inputs.values(), *stage.outputs.values()]:
                artifact = artifacts[node]
                if artifact.kind.startswith(("eeg.", "mri.", "fmri.", "source.")):
                    expected_units = {"values": "1"}
                    if artifact.kind.startswith("eeg."):
                        expected_units = (
                            {"density": "V^2/Hz", "frequency": "Hz"}
                            if artifact.kind == "eeg.psd"
                            else {"power": "V^2"}
                            if artifact.kind == "eeg.bands"
                            else {"voltage": "V"}
                        )
                    if artifact.kind == "fmri.contrast":
                        expected_units = {
                            "effect": "BOLD/regressor",
                            "variance": "(BOLD/regressor)^2",
                        }
                    if artifact.metadata["units"] != expected_units:
                        raise WorkflowError(
                            "Registered operation requires its explicit native units"
                        )
                if artifact.kind == "mri.labels" and artifact.metadata.get("ontology") != {
                    "0": "background",
                    "1": "heuristic-foreground",
                }:
                    raise WorkflowError(
                        "Threshold segmentation ontology cannot claim tissue identity"
                    )
            if stage.implementation == "eeg.reference":
                if any(
                    artifacts[n].metadata["reference"] != stage.parameters.get("reference")
                    for n in stage.outputs.values()
                ):
                    raise WorkflowError(
                        "EEG reference declaration differs from requested operation"
                    )
            elif stage.implementation.startswith("eeg."):
                if any(m["fs_hz"] != 160.0 or m["channels"] != ["C3", "C4"] for m in connected):
                    raise WorkflowError("Bounded EEG stage sampling/channel contract differs")
                if connected and any(
                    m["reference"] != connected[0]["reference"] for m in connected
                ):
                    raise WorkflowError("EEG reference mismatch across computation ports")
            if op.stochastic and stage.seed is None:
                raise WorkflowError("Stochastic stage requires explicit seed/stream")
        return order


def environment() -> dict[str, Any]:
    names = [
        "soma-neuro",
        "numpy",
        "scipy",
        "nilearn",
        "mne",
        "nibabel",
        "SimpleITK",
        "scikit-image",
        "neurodsp",
        "pandas",
        "scikit-learn",
        "joblib",
        "threadpoolctl",
    ]
    records = {}
    for name in names:
        if name == "soma-neuro":
            continue  # Soma uses the actual Python source digest, including editable installs.
        record = distribution(name).read_text("RECORD")
        if not record:
            raise WorkflowError(
                "Scientific dependency installation record unavailable; reuse unsafe"
            )
        records[name] = hashlib.sha256(record.encode()).hexdigest()
    builds = {}
    for name, module in [("numpy", np), ("scipy", scipy)]:
        config = getattr(module.__config__, "CONFIG", None)
        if not isinstance(config, dict):
            raise WorkflowError("Numerical build metadata unavailable; reuse unsafe")
        builds[name] = hashlib.sha256(canonical(config)).hexdigest()
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "byteorder": sys.byteorder,
        "os_build": platform.platform(),
        "kernel_build": platform.version(),
        "python_implementation": platform.python_implementation(),
        "python_compiler": platform.python_compiler(),
        "libraries": {n: version(n) for n in names},
        "installation_records_sha256": records,
        "numerical_build_metadata_sha256": builds,
        "backends": [
            {
                k: v
                for k, v in b.items()
                if k in {"internal_api", "version", "architecture", "threading_layer"}
            }
            for b in threadpool_info()
        ],
        "numerical_limits": {"workers": 1, "threads": 1},
        "policy": "exact-environment-v1; replay equivalence does not authorize cache interchange",
        "evidence_limit": "installation/build metadata are not authentication of a hostile runtime",
    }


def identities(graph: Graph, registry: Registry, env: dict[str, Any]) -> dict[str, Any]:
    artifacts = {a.id: a for a in graph.artifacts}
    derivations = {
        a.id: digest({"kind": a.kind, "metadata": a.metadata, "content": a.fingerprint})
        for a in graph.artifacts
        if a.producer is None
    }
    logical_derivations = dict(derivations)
    result = {}
    for stage in registry.validate(graph):
        inputs = {
            port: {
                "identity": logical_derivations[node],
                "kind": artifacts[node].kind,
                "metadata": artifacts[node].metadata,
            }
            for port, node in stage.inputs.items()
        }
        logical = {
            "algorithm": KEY_ALGORITHM,
            "implementation": stage.implementation,
            "source_sha256": registry.source,
            "operation_source_sha256": hashlib.sha256(
                inspect.getsource(registry.operations[stage.implementation].calculate).encode()
            ).hexdigest(),
            "algorithm_version": stage.algorithm_version,
            "producer_version": __version__,
            "software": env["libraries"],
            "inputs": inputs,
            "parameters": stage.parameters,
            "seed": stage.seed,
            "stream": stage.stream,
            "precision": stage.precision,
            "execution": stage.execution,
            "outputs": {
                p: {"kind": artifacts[n].kind, "metadata": artifacts[n].metadata}
                for p, n in stage.outputs.items()
            },
        }
        logical_key, environment_key = digest(logical), digest(env)
        key = digest(
            {
                "algorithm": KEY_ALGORITHM,
                "logical": logical_key,
                "environment": environment_key,
                "inputs": {p: derivations[n] for p, n in stage.inputs.items()},
                "node_binding": {
                    "stage": stage.id,
                    "inputs": stage.inputs,
                    "outputs": stage.outputs,
                },
            }
        )
        output_ids = {
            n: digest({"producer": key, "port": p, "contract": logical["outputs"][p]})
            for p, n in stage.outputs.items()
        }
        derivations.update(output_ids)
        logical_derivations.update(
            {
                n: digest({"producer": logical_key, "port": p, "contract": logical["outputs"][p]})
                for p, n in stage.outputs.items()
            }
        )
        result[stage.id] = {
            "cache_key": key,
            "logical_key": logical_key,
            "environment_key": environment_key,
            "logical": logical,
            "input_identities": {p: derivations[n] for p, n in stage.inputs.items()},
            "output_derivations": output_ids,
        }
    return result


def _string_keys(x: Any) -> None:
    if isinstance(x, dict):
        if any(type(k) is not str for k in x):
            raise WorkflowError("Workflow value mappings require explicit string keys")
        for v in x.values():
            _string_keys(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _string_keys(v)
    elif hasattr(x, "metadata"):
        _string_keys(x.metadata)


def normalized(value: Any) -> Any:
    """Snapshot the shared nonpickle codec before external input consumption."""
    _string_keys(value)
    numeric_bytes(value)
    arrays: dict[str, Any] = {}
    encoded = json.loads(canonical(encode(value, arrays, {})))
    copied = {k: np.array(a, copy=True) for k, a in arrays.items()}
    for a in copied.values():
        a.flags.writeable = False
    return decode(encoded, copied, {})


def content(value: Any) -> str:
    _string_keys(value)
    arrays: dict[str, Any] = {}
    metadata = encode(value, arrays, {})
    from soma.sdk.provenance import array_fingerprint

    def bound(x: Any) -> Any:
        if isinstance(x, dict):
            return {
                k: (array_fingerprint(arrays[v]) if k in {"__array__", "__volume__"} else bound(v))
                for k, v in x.items()
            }
        if isinstance(x, list):
            return [bound(v) for v in x]
        return x

    return digest(bound(metadata))


def numeric_bytes(value: Any) -> int:
    """Bound live numerical payloads; custom registered code is not an OS sandbox."""
    arrays: dict[str, Any] = {}
    metadata = encode(value, arrays, {})
    if len(canonical(metadata)) > 2 * 1024**2:
        raise WorkflowError("Workflow value metadata exceeds 2 MiB")
    total = 0
    for array in arrays.values():
        a = np.asarray(array)
        if (
            a.dtype.kind not in "biuf"
            or a.dtype.itemsize > 8
            or a.ndim > 5
            or a.nbytes > 64 * 1024**2
            or not np.isfinite(a).all()
        ):
            raise WorkflowError("Numerical workflow value violates finite bounded array policy")
        total += a.nbytes
    if total > 256 * 1024**2:
        raise WorkflowError("Live numerical workflow payload exceeds 256 MiB")
    return total


def safe_root(root: Path, *, create: bool = False) -> Path:
    absolute = root.absolute()
    system_aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
    for part in [absolute, *absolute.parents]:
        trusted_alias = (
            platform.system() == "Darwin"
            and part in system_aliases
            and part.resolve() == system_aliases[part]
        )
        if part.is_symlink() and not trusted_alias:
            raise WorkflowError("Symlinked workflow root rejected")
    if create:
        absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not absolute.is_dir():
        raise WorkflowError("Explicit existing allowed root required")
    return absolute.resolve(strict=True)


def permitted(root: Path, reference: str) -> Path:
    relative(reference)
    root = safe_root(root)
    path = root / reference
    for component in [path, *path.parents]:
        if component == root:
            break
        if component.is_symlink():
            raise WorkflowError("Symlinked resource rejected")
    if not path.resolve(strict=True).is_relative_to(root):
        raise WorkflowError("Resource outside allowed root")
    return path


def envelope(
    artifact: Artifact,
    stage: Stage,
    identity: dict[str, Any],
    value: Any,
    env: dict[str, Any],
    observed_inputs: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    arrays: dict[str, Any] = {}
    encoded = encode(value, arrays, {})
    metadata = artifact.metadata
    result = create_result(
        "experiment.manifest",
        {
            "computation": stage.implementation,
            "inputs": {},
            "environment": env,
            "assumptions": ["explicit typed workflow contracts; numerical checks only"],
            "validation": {
                "serialization": "checked before publication",
                "stage_contract": "VALIDATED_NUMERICAL",
            },
            "limitations": metadata["limitations"] + metadata["restrictions"],
        },
        arrays=arrays,
        values=encoded,
        interpretation_state="VALIDATED_NUMERICAL",
        method={"id": stage.implementation, "version": stage.algorithm_version},
        parameters=stage.parameters,
        units=metadata["units"],
        dataset_identity=metadata["dataset_identity"],
        subject_identity=metadata["subject_identity"],
        spatial_reference=metadata["spatial_reference"],
        temporal_reference=metadata["temporal_reference"],
        statistical_estimand=metadata["estimand"],
        provenance={
            "workflow": {
                "cache_key": identity["cache_key"],
                "logical_key": identity["logical_key"],
                "environment_key": identity["environment_key"],
                "input_identities": identity["input_identities"],
                "input_contents": observed_inputs,
                "derivation": identity["output_derivations"][artifact.id],
                "kind": artifact.kind,
                "scientific_metadata": metadata,
                "content": content(value),
                "artifact_identity": digest(
                    {
                        "derivation": identity["output_derivations"][artifact.id],
                        "content": content(value),
                    }
                ),
            }
        },
    )
    return result, arrays


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def lookup(
        self,
        stage: Stage,
        identity: dict[str, Any],
        artifacts: dict[str, Artifact],
        env: dict[str, Any],
        observed_inputs: dict[str, str],
    ) -> dict[str, Any] | None:
        if not self.root.exists():
            return None
        root = safe_root(self.root)
        entry = root / identity["cache_key"]
        if not entry.exists() and not entry.is_symlink():
            return None
        try:
            if entry.is_symlink():
                raise WorkflowError("Symlinked cache entry")
            receipt = read_json(entry / "receipt.json")
            if receipt != {
                "schema": "soma.workflow.cache/1",
                "identity": identity,
                "outputs": stage.outputs,
                "producer_version": __version__,
                "input_contents": observed_inputs,
            }:
                raise WorkflowError("Stale or conflicting cache receipt")
            values = {}
            for port, node in stage.outputs.items():
                path = permitted(entry, port + "/result.json")
                result, arrays = load_result(path)
                value = decode(result["payload"]["values"], arrays, {})
                expected, _ = envelope(
                    artifacts[node], stage, identity, value, env, observed_inputs
                )
                if result["producer_version"] != __version__ or (
                    result["provenance"] != expected["provenance"]
                    or not compare_results(result, expected)["compatible"]
                ):
                    raise WorkflowError("Cache artifact lineage, producer or scientific mismatch")
                values[port] = value
            return values
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise WorkflowError(
                "Published cache failed verification; no automatic repair"
            ) from error

    def publish(
        self,
        stage: Stage,
        identity: dict[str, Any],
        artifacts: dict[str, Artifact],
        values: dict[str, Any],
        env: dict[str, Any],
        fault: Fault,
        observed_inputs: dict[str, str],
    ) -> None:
        root = safe_root(self.root, create=True)
        fd = os.open(root / ".publication.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise WorkflowError("Invalid publication lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            old = self.lookup(stage, identity, artifacts, env, observed_inputs)
            if old is not None:
                if content(old) != content(values):
                    raise WorkflowError("Conflicting content for identical stage identity")
                return
            pending = Path(tempfile.mkdtemp(prefix=".building-", dir=root))
            try:
                for port, node in stage.outputs.items():
                    result, arrays = envelope(
                        artifacts[node], stage, identity, values[port], env, observed_inputs
                    )
                    fault(stage.id, "serialization")
                    save_result(result, arrays, pending / port)
                (pending / "receipt.json").write_bytes(
                    canonical(
                        {
                            "schema": "soma.workflow.cache/1",
                            "identity": identity,
                            "outputs": stage.outputs,
                            "producer_version": __version__,
                            "input_contents": observed_inputs,
                        }
                    )
                )
                for path in pending.rglob("*"):
                    if path.is_file():
                        with path.open("rb") as stream:
                            os.fsync(stream.fileno())
                for path in [
                    *sorted((p for p in pending.rglob("*") if p.is_dir()), reverse=True),
                    pending,
                ]:
                    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                fault(stage.id, "before_publication")
                # Same-filesystem nonempty directory publication. Existing entries never replaced.
                os.rename(pending, root / identity["cache_key"])
                descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                fault(stage.id, "after_publication")
            finally:
                if pending.exists():
                    shutil.rmtree(pending)
        finally:
            os.close(fd)


class Executor:
    """Single worker, bounded payloads, cooperative cancellation and verified resume."""

    def __init__(
        self,
        registry: Registry,
        cache_root: Path,
    ) -> None:
        self.registry = registry
        self.cache = Cache(cache_root)
        self.environment = environment()

    def plan(self, graph: Graph) -> dict[str, Any]:
        keys = identities(graph, self.registry, self.environment)
        artifacts = {a.id: a for a in graph.artifacts}
        rows = []
        observed = {a.id: a.fingerprint for a in graph.artifacts if a.producer is None}
        for stage in self.registry.validate(graph):
            missing = any(n not in observed for n in stage.inputs.values())
            expected = {p: str(observed[n]) for p, n in stage.inputs.items()} if not missing else {}
            hit = (
                None
                if missing
                else self.cache.lookup(stage, keys[stage.id], artifacts, self.environment, expected)
            )
            if hit is not None:
                observed.update({stage.outputs[p]: content(v) for p, v in hit.items()})
            rows.append(
                {
                    "stage": stage.id,
                    "status": "VERIFIED_HIT" if hit is not None else "MISS",
                    "reason": "full integrity and lineage verified"
                    if hit is not None
                    else "no entry for exact computation and environment",
                    **keys[stage.id],
                }
            )
        return {
            "schema": "soma.workflow.plan/1",
            "graph": graph.id,
            "stages": rows,
            "execution_started": False,
            "external_input_integrity": "declared fingerprints only; run verifies current inputs",
        }

    def run(
        self,
        graph: Graph,
        *,
        inputs: dict[str, Any] | None = None,
        input_root: Path | None = None,
        cancelled: Callable[[], bool] | None = None,
        fault: Fault | None = None,
        record: Path | None = None,
        previous: Graph | None = None,
    ) -> dict[str, Any]:
        # Snapshot declarations before execution; callers cannot mutate key semantics mid-run.
        graph = Graph.from_dict(graph.to_dict())
        order = self.registry.validate(graph)
        impact = invalidation(previous, graph) if previous is not None else None
        if input_root is not None:
            source_root = safe_root(input_root)
            if self.cache.root.resolve().is_relative_to(source_root) or (
                record is not None and record.resolve().is_relative_to(source_root)
            ):
                raise WorkflowError("Workflow outputs cannot modify an input dataset root")
        keys = identities(graph, self.registry, self.environment)
        artifacts = {a.id: a for a in graph.artifacts}
        values: dict[str, Any] = {}
        for artifact in graph.artifacts:
            if artifact.producer is not None:
                continue
            if inputs is not None and artifact.id in inputs:
                value = normalized(inputs[artifact.id])
            elif input_root is not None and artifact.reference:
                result, arrays = load_result(permitted(input_root, artifact.reference))
                if result["interpretation_state"] != "VALIDATED_NUMERICAL":
                    raise WorkflowError("Input validation is INDETERMINATE")
                declared = result["provenance"].get("workflow", {})
                if (
                    declared.get("kind") != artifact.kind
                    or declared.get("scientific_metadata") != artifact.metadata
                ):
                    raise WorkflowError("Input scientific type/metadata mismatch")
                value = decode(result["payload"]["values"], arrays, {})
            else:
                raise WorkflowError("Required input unavailable; no computation started")
            if content(value) != artifact.fingerprint:
                raise WorkflowError("Input content fingerprint mismatch; no computation started")
            values[artifact.id] = value
        numeric_bytes(values)
        fingerprints = {n: content(v) for n, v in values.items()}
        consumers = {a.id: sum(a.id in s.inputs.values() for s in order) for a in graph.artifacts}
        stop = cancelled or (lambda: False)
        hook = fault or (lambda stage, point: None)
        rows = []
        status = "COMPLETE"
        for stage in order:
            started = time.perf_counter()
            row: dict[str, Any] = {
                "stage": stage.id,
                "cache_key": keys[stage.id]["cache_key"],
                "validation": "NOT_RUN",
                "cached": False,
            }
            try:
                hook(stage.id, "before_stage")
                if stop():
                    raise InterruptedError("Cooperative cancellation")
                observed_inputs = {p: content(values[n]) for p, n in stage.inputs.items()}
                outputs = self.cache.lookup(
                    stage, keys[stage.id], artifacts, self.environment, observed_inputs
                )
                if outputs is None:
                    hook(stage.id, "computation")
                    selected = {p: values[n] for p, n in stage.inputs.items()}
                    with _SCIENCE_LOCK, threadpool_limits(limits=1):
                        outputs = self.registry.operations[stage.implementation].calculate(
                            selected, stage.parameters, stage.seed
                        )
                    if set(outputs) != set(stage.outputs):
                        raise WorkflowError(
                            "Calculated output ports differ from registered contract"
                        )
                    if stop():
                        raise InterruptedError("Cooperative cancellation before publication")
                    numeric_bytes({"live": values, "new": outputs})
                    self.cache.publish(
                        stage,
                        keys[stage.id],
                        artifacts,
                        outputs,
                        self.environment,
                        hook,
                        observed_inputs,
                    )
                    # Fresh and cached paths both consume identical serialized snapshots.
                    outputs = self.cache.lookup(
                        stage, keys[stage.id], artifacts, self.environment, observed_inputs
                    )
                    if outputs is None:
                        raise WorkflowError("Publication did not produce a verified entry")
                else:
                    row["cached"] = True
                values.update({stage.outputs[p]: v for p, v in outputs.items()})
                fingerprints.update({stage.outputs[p]: content(v) for p, v in outputs.items()})
                for consumed in set(stage.inputs.values()):
                    consumers[consumed] -= 1
                    if consumers[consumed] == 0:
                        values.pop(consumed, None)
                for produced in stage.outputs.values():
                    if consumers[produced] == 0:
                        values.pop(produced, None)
                row.update(status="COMPLETE", validation="FORMAT_INTEGRITY_LINEAGE_VERIFIED")
                hook(stage.id, "before_status_update")
            except InterruptedError:
                row.update(status="CANCELLED", reason="cooperative cancellation")
                status = "CANCELLED"
            except Exception as error:
                row.update(
                    status="FAILED",
                    reason=(
                        str(error) if isinstance(error, WorkflowError) else type(error).__name__
                    ),
                )
                status = "FAILED"
            row["wall_s"] = time.perf_counter() - started
            rows.append(row)
            if status != "COMPLETE":
                break
        report = {
            "schema": "soma.workflow.run/1",
            "graph": graph.to_dict(),
            "invalidation": impact,
            "status": status,
            "environment": self.environment,
            "stages": rows,
            "outputs": fingerprints,
            "limitations": [
                "numerical lineage is not scientific or clinical certification",
                "cancellation occurs at stage/publication boundaries",
            ],
        }
        if record is not None:
            safe_root(record.parent, create=True)
            if record.is_symlink():
                raise WorkflowError("Symlinked run record rejected")
            atomic_json(record, report)
        return report

    def resume(self, graph: Graph, **kwargs: Any) -> dict[str, Any]:
        """Revalidate exact dependencies and published entries; never trust old journals."""
        return self.run(graph, **kwargs)
