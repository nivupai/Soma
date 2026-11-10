"""Controlled descriptive execution and drift; never grants cache/inference authorization."""

import hashlib
import json
import math
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

from soma.pipeline.cache import decode
from soma.protocol.binding import (
    Snapshot,
    conformance,
    environment_permitted,
    graph_for,
    registry,
    seed_for,
)
from soma.protocol.model import ProtocolError, SealedProtocol, closed, compare_protocols
from soma.results.contracts import canonical, create_result
from soma.results.io import inspect_result, load_result, save_result
from soma.workflow.model import digest
from soma.workflow.runtime import Executor, identities, safe_root

Mode = Literal["EXACT", "CONTROLLED", "EXPLORATORY"]


def utc() -> str:
    return datetime.now(UTC).isoformat()


def _validate_record(value: dict[str, Any]) -> None:
    try:
        closed(
            value,
            {
                "schema",
                "execution_id",
                "protocol",
                "snapshot",
                "sequence",
                "started_at",
                "finished_at",
                "mode",
                "replay_assessment",
                "status",
                "environment",
                "implementation_fingerprint",
                "members",
                "deviations",
                "interpretation",
                "record_sha256",
            },
        )
        if value["schema"] != "soma.protocol.execution/1.0.0" or value["mode"] not in {
            "EXACT",
            "CONTROLLED",
            "EXPLORATORY",
        }:
            raise ProtocolError("Unsupported execution record schema/mode")
        if value["interpretation"] != "DESCRIPTIVE_ONLY" or value["status"] not in {
            "COMPLETE",
            "PARTIAL",
            "BLOCKED",
        }:
            raise ProtocolError("Execution cannot assert confirmation or unknown completion")
        if type(value["sequence"]) is not int or value["sequence"] < 1:
            raise ProtocolError("Explicit positive run sequence required")
        start, end = (datetime.fromisoformat(value[k]) for k in ["started_at", "finished_at"])
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ProtocolError("Invalid explicit execution times")
        sealed = SealedProtocol(canonical(value["protocol"]))
        sealed.record()
        snapshot = Snapshot.from_dict(value["snapshot"])
        expected = {(m["unit_id"], m["session"]) for m in snapshot.document()["members"]}
        observed = {(m["unit_id"], m["session"]) for m in value["members"]}
        if expected != observed or len(observed) != len(value["members"]):
            raise ProtocolError("All prespecified units must remain in execution record")
        if value["status"] == "COMPLETE" and any(
            m["status"] != "COMPLETE" for m in value["members"]
        ):
            raise ProtocolError("Incomplete/missing outcomes cannot claim complete execution")
        env = value["environment"]
        for name in [
            "python",
            "system",
            "machine",
            "libraries",
            "os_build",
            "kernel_build",
            "python_compiler",
            "installation_records_sha256",
            "numerical_build_metadata_sha256",
        ]:
            if not env.get(name):
                raise ProtocolError("Missing verifiable software/build identity")
        from packaging.version import Version

        for software_version in env["libraries"].values():
            Version(software_version)
        for table in [env["installation_records_sha256"], env["numerical_build_metadata_sha256"]]:
            if not all(
                isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x)
                for x in table.values()
            ):
                raise ProtocolError("Invalid software build fingerprint")
        if not environment_permitted(sealed.protocol, env):
            raise ProtocolError("Recorded software/platform outside declared supported policy")
        if len(value["implementation_fingerprint"]) != 64:
            raise ProtocolError("Invalid implementation fingerprint")
        axes = sealed.protocol.document()["tolerances"]["axes"]
        for member in value["members"]:
            if member["status"] == "COMPLETE":
                if len(member["numerical_summary"]) != len(axes) or not all(
                    math.isfinite(x) for x in member["numerical_summary"]
                ):
                    raise ProtocolError("Outcome shape/missingness violates frozen policy")
                from soma.workflow.model import Graph

                actual = conformance(
                    sealed.protocol,
                    Graph.from_dict(member["graph"]),
                    snapshot=snapshot,
                    member=next(
                        m
                        for m in snapshot.document()["members"]
                        if (m["unit_id"], m["session"]) == (member["unit_id"], member["session"])
                    ),
                )
                if actual["status"] != "CONFORMANT" or not member["input_content_fingerprints"]:
                    raise ProtocolError(
                        "Execution settings do not conform to sealed scientific requirements"
                    )
                if member["conformance"]["status"] != "CONFORMANT":
                    raise ProtocolError("Nonconformant output cannot be valid")
        if (
            value["record_sha256"]
            != hashlib.sha256(
                canonical({k: v for k, v in value.items() if k != "record_sha256"})
            ).hexdigest()
        ):
            raise ProtocolError("Execution record checksum mismatch")
        if not value["environment"] or not value["implementation_fingerprint"]:
            raise ProtocolError("Missing execution software evidence")
    except ProtocolError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
        raise ProtocolError("Malformed scientific execution record") from error


@dataclass(frozen=True)
class Execution:
    _canonical: bytes

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Execution":
        _validate_record(value)
        return cls(canonical(value))

    def record(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        _validate_record(value)
        return dict(value)


def _summary(
    graph: Any, executor: Executor, run: dict[str, Any]
) -> tuple[list[float], dict[str, Any], dict[str, Any]]:
    keys = identities(graph, executor.registry, executor.environment)

    def get(stage: str, port: str) -> Any:
        artifact, arrays = load_result(
            executor.cache.root / keys[stage]["cache_key"] / port / "result.json"
        )
        return decode(artifact["payload"]["values"], arrays, {})

    reference = {}
    if "bands" in keys:
        values = get("bands", "bands")
        summary = [*values["mu"], *values["beta"]]
    elif "qc" in keys:
        summary = list(get("qc", "qc")["volumes_m3"].values())
        from soma.sdk.imaging import LabelVolume, Volume, score

        predicted = get("segment", "labels")
        xyz = np.indices(predicted.shape).transpose(1, 2, 3, 0)
        truth = Volume(
            (np.linalg.norm(xyz - 7.5, axis=-1) <= 5).astype(np.uint8), predicted.affine_m, "labels"
        )
        common: dict[str, Any] = {
            "subject": "synthetic",
            "space": "synthetic-native",
            "ontology": {1: "foreground"},
        }
        row = score(
            LabelVolume(
                predicted, **common, provenance={"method": "independent intensity prediction"}
            ),
            LabelVolume(
                truth,
                **common,
                provenance={"source": "independent analytic radius 5; not used for prediction"},
            ),
        )["labels"][0]
        reference = {k: row[k] for k in ["Dice", "Jaccard", "ASSD_mm", "HD95_mm"]}
        reference["scope"] = "synthetic analytic foreground only; not tissue/anatomical validation"
        reference["reference_used_in_prediction"] = False
    elif "roi" in keys:
        values = get("roi", "roi")
        summary = [values["mean_effect"], values["mean_variance"]]
    else:
        values = get("reconstruct", "source")
        summary = [*values["estimate"], *values["resolution_diagonal"]]
    files = {}
    for stage in graph.stages:
        folder = executor.cache.root / keys[stage.id]["cache_key"]
        files[stage.id] = {
            str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*"))
            if p.is_file()
        }
    return np.asarray(summary, dtype=float).tolist(), files, reference


def plan(
    sealed: SealedProtocol,
    snapshot: Snapshot,
    *,
    mode: Mode = "EXACT",
    cache_root: Path = Path("reports/protocol-cache"),
    reference: Execution | None = None,
) -> dict[str, Any]:
    p = sealed.protocol
    d = p.document()
    executor = Executor(registry(), cache_root)
    if mode in {"CONTROLLED", "EXPLORATORY"} and reference is None:
        raise ProtocolError("Controlled/exploratory replay requires a baseline execution")
    if mode == "EXPLORATORY" and "amendment" not in d:
        raise ProtocolError("Exploratory replay requires an explicit new protocol revision")
    if reference is not None:
        baseline = reference.record()
        prior = SealedProtocol(canonical(baseline["protocol"])).protocol
        revisions = compare_protocols(prior, p)
        if baseline["status"] != "COMPLETE":
            raise ProtocolError("Incomplete baseline cannot authorize replay")
        if mode == "EXACT" and (
            prior.fingerprint != p.fingerprint
            or Snapshot.from_dict(baseline["snapshot"]).fingerprint != snapshot.fingerprint
            or digest(baseline["environment"]) != digest(executor.environment)
        ):
            raise ProtocolError("EXACT protocol/snapshot/environment requirements differ")
        if mode == "CONTROLLED":
            if revisions["scientific_change"]:
                raise ProtocolError("Scientific amendment cannot masquerade as controlled replay")
            old = Snapshot.from_dict(baseline["snapshot"]).document()
            current = snapshot.document()
            axes = d["replay_policy"]["controlled_axes"]
            if prior.fingerprint != p.fingerprint and (
                not revisions["explicit_parent_amendment"]
                or not revisions["version_declaration_valid"]
                or "editorial_revision" not in axes
            ):
                raise ProtocolError("Protocol revision is not an authorized compatible amendment")
            old_sessions = {(m["unit_id"], m["session"]) for m in old["members"]}
            new_sessions = {(m["unit_id"], m["session"]) for m in current["members"]}
            if old_sessions - new_sessions and "session" not in axes:
                raise ProtocolError("New session was not prespecified")

            if old != current and "snapshot" not in axes:
                raise ProtocolError("Snapshot change was not prespecified")
            old_units = {m["unit_id"] for m in old["members"]}
            new_units = {m["unit_id"] for m in current["members"]}
            if old_units - new_units or (new_units - old_units and "added_units" not in axes):
                raise ProtocolError("Selective removal/addition violates frozen unit policy")
            if (
                digest(baseline["environment"]) != digest(executor.environment)
                and "environment" not in axes
            ):
                raise ProtocolError("Environment change not prespecified")
        if mode == "EXPLORATORY" and (
            not revisions["explicit_parent_amendment"] or not revisions["version_declaration_valid"]
        ):
            raise ProtocolError("Invalid explicit exploratory amendment")
        if baseline["implementation_fingerprint"] != executor.registry.source:
            raise ProtocolError(
                "Implementation source changed without authorized compatibility evidence"
            )
    scheduled = [seed_for(p, m["unit_id"], m["session"]) for m in snapshot.document()["members"]]
    if len(set(scheduled)) != len(scheduled):
        raise ProtocolError("Seed schedule collision would break independent realization streams")
    rows = []
    for member in snapshot.document()["members"]:
        graph = graph_for(p, snapshot, member)
        check = conformance(p, graph, snapshot=snapshot, member=member)
        rows.append(
            {
                "unit_id": member["unit_id"],
                "session": member["session"],
                "graph_identity": digest(graph.to_dict()),
                "conformance": check,
                "available": member["available"],
            }
        )
    if mode not in {"EXACT", "CONTROLLED", "EXPLORATORY"}:
        raise ProtocolError("Unknown replay mode")
    if not environment_permitted(p, executor.environment):
        raise ProtocolError("Actual environment outside prespecified supported matrix")
    return {
        "protocol_fingerprint": p.fingerprint,
        "snapshot_fingerprint": snapshot.fingerprint,
        "mode": mode,
        "units": rows,
        "execution_started": False,
        "status": "READY"
        if all(r["conformance"]["status"] == "CONFORMANT" for r in rows)
        else "BLOCKED",
        "interpretation": "DESCRIPTIVE_ONLY",
        "cache_interchangeability": False,
        "requirements": len(d["requirements"]["stages"]),
    }


def run(
    sealed: SealedProtocol,
    snapshot: Snapshot,
    cache_root: Path,
    *,
    sequence: int,
    mode: Mode = "EXACT",
    reference: Execution | None = None,
) -> Execution:
    if type(sequence) is not int or sequence < 1:
        raise ProtocolError("Explicit positive sequence required")
    prepared = plan(sealed, snapshot, mode=mode, cache_root=cache_root, reference=reference)
    p = sealed.protocol
    started = utc()
    executor = Executor(registry(), cache_root)
    members = []
    deviations = []
    for member, planned in zip(snapshot.document()["members"], prepared["units"], strict=True):
        row = {
            "unit_id": member["unit_id"],
            "session": member["session"],
            "status": "MISSING",
            "conformance": planned["conformance"],
            "numerical_summary": None,
            "input_content_fingerprints": {},
            "artifact_content_fingerprints": {},
            "artifact_file_fingerprints": {},
            "qc": {},
            "missingness": member["reason"],
        }
        if planned["conformance"]["status"] != "CONFORMANT":
            row["status"] = "BLOCKED"
            deviations.extend(planned["conformance"]["deviations"])
        elif not member["available"]:
            deviations.append(
                {
                    "category": "MISSING_UNIT_DATA",
                    "stage": "input",
                    "original_policy": "all prespecified units retained",
                    "observed_behavior": member["reason"],
                    "evidence": {"unit_id": member["unit_id"], "session": member["session"]},
                    "scientific_consequence": "comparison indeterminate; denominator retained",
                    "resolution_status": "UNRESOLVED",
                    "authorized_amendment_reference": None,
                }
            )
        else:
            graph = graph_for(p, snapshot, member)
            wf = executor.run(graph)
            row["graph_identity"] = digest(graph.to_dict())
            row["workflow_semantics"] = digest(p.document()["requirements"])
            row["graph"] = graph.to_dict()
            row["qc"] = {"stages": wf["stages"], "all_complete": wf["status"] == "COMPLETE"}
            if wf["status"] == "COMPLETE":
                summary, files, reference_metrics = _summary(graph, executor, wf)
                row.update(
                    status="COMPLETE",
                    numerical_summary=summary,
                    artifact_content_fingerprints=wf["outputs"],
                    artifact_file_fingerprints=files,
                    independent_reference=reference_metrics,
                )
                inputs = {
                    n: h
                    for n, h in wf["outputs"].items()
                    if n.startswith("generate-") or n == "geometry-geometry"
                }
                row["input_content_fingerprints"] = inputs
                row["missingness"] = None
            else:
                row["status"] = "FAILED"
                deviations.append(
                    {
                        "category": "PARTIAL_WORKFLOW",
                        "stage": wf["stages"][-1]["stage"],
                        "original_policy": "all stages verified",
                        "observed_behavior": wf["stages"][-1].get("reason"),
                        "evidence": {"unit_id": member["unit_id"]},
                        "scientific_consequence": "incomplete outcomes not comparable",
                        "resolution_status": "UNRESOLVED",
                        "authorized_amendment_reference": None,
                    }
                )
        members.append(row)
    value: dict[str, Any] = {
        "schema": "soma.protocol.execution/1.0.0",
        "execution_id": uuid.uuid4().hex,
        "protocol": sealed.record(),
        "snapshot": snapshot.document(),
        "sequence": sequence,
        "started_at": started,
        "finished_at": utc(),
        "mode": mode,
        "replay_assessment": {
            "reference_execution_id": reference.record()["execution_id"] if reference else None,
            "status": "INITIAL_CAPTURE" if reference is None else "PENDING",
        },
        "status": "COMPLETE" if all(m["status"] == "COMPLETE" for m in members) else "PARTIAL",
        "environment": executor.environment,
        "implementation_fingerprint": executor.registry.source,
        "members": members,
        "deviations": deviations,
        "interpretation": "DESCRIPTIVE_ONLY",
    }
    value["record_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    preliminary = Execution.from_dict(value)
    if reference is not None:
        assessment = compare(reference, preliminary, mode=mode)
        value["replay_assessment"]["status"] = assessment["status"]
        value["replay_assessment"]["authorized"] = assessment["authorized"]
        value["replay_assessment"]["reasons"] = assessment["reasons"]
        if not assessment["authorized"]:
            value["deviations"].append(
                {
                    "category": "REPLAY_POSTCHECK_FAILED",
                    "stage": "replay",
                    "original_policy": mode,
                    "observed_behavior": assessment["reasons"],
                    "evidence": "post-execution identity/numerical comparison",
                    "scientific_consequence": "not an authorized replication",
                    "resolution_status": "UNRESOLVED",
                    "authorized_amendment_reference": None,
                }
            )
        value["record_sha256"] = hashlib.sha256(
            canonical({k: v for k, v in value.items() if k != "record_sha256"})
        ).hexdigest()
    return Execution.from_dict(value)


def compare(left: Execution, right: Execution, *, mode: Mode = "EXACT") -> dict[str, Any]:
    a, b = left.record(), right.record()
    pa = SealedProtocol(canonical(a["protocol"])).protocol
    pb = SealedProtocol(canonical(b["protocol"])).protocol
    pd = compare_protocols(pa, pb)
    policy = pa.document()["replay_policy"]
    bounds = pa.document()["tolerances"]
    axes_match = (
        bounds["axes"] == pb.document()["tolerances"]["axes"]
        and bounds["units"] == pb.document()["tolerances"]["units"]
    )
    sa, sb = Snapshot.from_dict(a["snapshot"]), Snapshot.from_dict(b["snapshot"])
    ma = {(m["unit_id"], m["session"]): m for m in a["members"]}
    mb = {(m["unit_id"], m["session"]): m for m in b["members"]}
    shared = ma.keys() & mb.keys()
    added = mb.keys() - ma.keys()
    removed = ma.keys() - mb.keys()
    env_diff = digest(a["environment"]) != digest(b["environment"])
    impl_diff = a["implementation_fingerprint"] != b["implementation_fingerprint"]
    input_content_changed = any(
        ma[n]["input_content_fingerprints"] != mb[n]["input_content_fingerprints"]
        for n in shared
        if ma[n]["status"] == mb[n]["status"] == "COMPLETE"
    )
    data_diff = sa.fingerprint != sb.fingerprint or input_content_changed
    missing = a["status"] != "COMPLETE" or b["status"] != "COMPLETE"
    reasons = []
    if mode == "EXACT":
        if pa.fingerprint != pb.fingerprint:
            reasons.append("protocol identity differs")
        if sa.fingerprint != sb.fingerprint or data_diff or added or removed:
            reasons.append("snapshot/input identity differs")
        if env_diff:
            reasons.append("exact environment differs")
    elif mode == "CONTROLLED":
        if pd["scientific_change"]:
            reasons.append("unapproved scientific protocol amendment")
        if pa.fingerprint != pb.fingerprint and not (
            pd["explicit_parent_amendment"]
            and pd["version_declaration_valid"]
            and "editorial_revision" in policy["controlled_axes"]
        ):
            reasons.append("unapproved protocol revision")
        if data_diff and "snapshot" not in policy["controlled_axes"]:
            reasons.append("snapshot change not prespecified")
        if added and "added_units" not in policy["controlled_axes"]:
            reasons.append("additional units not prespecified")
        if removed and not (
            "session" in policy["controlled_axes"]
            and {n[0] for n in removed} <= {n[0] for n in added}
        ):
            reasons.append("selective unit removal not authorized")
        if env_diff and (
            "environment" not in policy["controlled_axes"]
            or not environment_permitted(pa, b["environment"])
        ):
            reasons.append("environment change not prespecified/supported")
        if sa.document()["namespace"] != sb.document()["namespace"]:
            reasons.append("dataset namespace differs")
    elif mode == "EXPLORATORY":
        if not pd["explicit_parent_amendment"] or not pd["version_declaration_valid"]:
            reasons.append("explicit identifiable new protocol amendment required")
    else:
        raise ProtocolError("Unknown replay mode")
    if impl_diff:
        reasons.append("implementation source changed; no compatible-implementation policy")
    if missing:
        reasons.append("missing or incomplete outcomes")
    if not axes_match:
        reasons.append("outcome axes or physical units differ")
    rows = []
    all_equal = not added and not removed
    all_close = bool(shared) and not added and not removed
    same_inputs = True
    outcome_changed = False
    for n in sorted(shared):
        x, y = ma[n], mb[n]
        if x["status"] != "COMPLETE" or y["status"] != "COMPLETE" or not axes_match:
            all_equal = False
            all_close = False
            continue
        u, v = np.asarray(x["numerical_summary"]), np.asarray(y["numerical_summary"])
        if u.shape != v.shape:
            raise ProtocolError("Outcome array shapes differ")
        input_equal = x["input_content_fingerprints"] == y["input_content_fingerprints"]
        same_inputs &= input_equal
        equal = bool(np.array_equal(u, v))
        close = bool(np.allclose(u, v, atol=bounds["atol"], rtol=bounds["rtol"]))
        maximum = float(np.max(np.abs(u - v)))
        outcome_changed |= not equal
        applicable = input_equal and not pd["scientific_change"] and not impl_diff
        rows.append(
            {
                "unit_id": n[0],
                "session": n[1],
                "same_inputs": input_equal,
                "axes": bounds["axes"],
                "units": bounds["units"],
                "left_values": u.tolist(),
                "right_values": v.tolist(),
                "maximum_absolute_error": maximum,
                "numerically_identical": equal,
                "numerically_equivalent": close if applicable else None,
                "equivalence_applicable": applicable,
                "atol": bounds["atol"],
                "rtol": bounds["rtol"],
                "comparison_scope": (
                    "selected summaries only, not statistical significance or biological drift"
                ),
            }
        )
        all_equal &= equal
        all_close &= close and applicable
    if not same_inputs and mode == "EXACT":
        reasons.append("observed input fingerprints differ")
    numeric_applicable = (
        not input_content_changed
        and not added
        and not removed
        and not pd["scientific_change"]
        and not impl_diff
        and not missing
        and axes_match
    )
    if numeric_applicable and not all_close:
        reasons.append("frozen numerical tolerance exceeded")
    drift = []
    for changed, category, evidence in [
        (
            data_diff,
            "DATA_DRIFT",
            {
                "added_units": [list(n) for n in sorted(added)],
                "removed_units": [list(n) for n in sorted(removed)],
                "snapshot_identity_changed": sa.fingerprint != sb.fingerprint,
                "input_content_changed": input_content_changed,
            },
        ),
        (pd["scientific_change"], "PROTOCOL_DRIFT", pd),
        (
            impl_diff,
            "IMPLEMENTATION_DRIFT",
            {"left": a["implementation_fingerprint"], "right": b["implementation_fingerprint"]},
        ),
        (
            env_diff,
            "EXECUTION_ENVIRONMENT_DRIFT",
            {"versions_changed": a["environment"]["libraries"] != b["environment"]["libraries"]},
        ),
        (
            numeric_applicable and not all_equal,
            "NUMERICAL_DRIFT",
            {"within_frozen_bounds": all_close},
        ),
        (
            outcome_changed,
            "MEASUREMENT_OR_OUTCOME_DRIFT",
            {"biological_interpretation": "NOT_ESTABLISHED"},
        ),
        (
            missing or not shared,
            "MISSING_OR_UNVERIFIABLE_EVIDENCE",
            {"missing_or_incomplete": missing},
        ),
    ]:
        if changed:
            drift.append(
                {
                    "category": category,
                    "observed": evidence,
                    "evidence_scope": "declared protocols and verified execution records",
                }
            )
    return {
        "schema": "soma.protocol.comparison/1.0.0",
        "mode": mode,
        "authorized": not reasons,
        "status": "INDETERMINATE"
        if missing
        else "REJECTED"
        if reasons
        else "EXPLORATORY_DESCRIPTIVE"
        if mode == "EXPLORATORY"
        else "CONTROLLED_DATA_CHANGE"
        if data_diff
        else "NUMERICALLY_EQUIVALENT",
        "reasons": reasons,
        "protocol_comparison": pd,
        "drift": drift,
        "numerical_comparisons": rows,
        "artifact_byte_identical": bool(shared)
        and not missing
        and not added
        and not removed
        and all(
            ma[n]["artifact_file_fingerprints"] == mb[n]["artifact_file_fingerprints"]
            for n in shared
        ),
        "numerically_identical": all_equal if numeric_applicable else None,
        "numerically_equivalent": all_close if numeric_applicable else None,
        "numerical_equivalence_applicable": numeric_applicable,
        "unit_counts": {
            "left": len(ma),
            "right": len(mb),
            "shared": len(shared),
            "added": len(added),
            "removed": len(removed),
        },
        "cache_interchangeability": False,
        "confirmatory_replication_authorized": False,
        "interpretation": (
            "descriptive; repeated executions are not automatically human longitudinal measurements"
        ),
    }


def write_execution(execution: Execution, directory: Path) -> Path:
    value = execution.record()
    p = SealedProtocol(canonical(value["protocol"])).protocol.document()
    envelope = create_result(
        "experiment.manifest",
        {
            "computation": "protocol-controlled-replay",
            "inputs": {},
            "environment": value["environment"],
            "assumptions": ["explicit frozen local declarations"],
            "validation": {"execution": "verified", "status": value["status"]},
            "limitations": p["scientific"]["limitations"],
        },
        values=value,
        provenance={"protocol_fingerprint": value["protocol"]["protocol_fingerprint"]},
        interpretation_state="DESCRIPTIVE_ONLY"
        if value["status"] == "COMPLETE"
        else "INDETERMINATE",
        method={"id": "soma.protocol.replay", "version": "1"},
        parameters={},
        units={},
        dataset_identity=value["snapshot"]["namespace"],
        subject_identity=None,
        spatial_reference=None,
        temporal_reference=None,
        statistical_estimand=p["scientific"]["estimand"],
    )
    parent = safe_root(directory.parent, create=True)
    if directory.exists() or directory.is_symlink():
        raise ProtocolError("Immutable execution destination exists")
    with tempfile.TemporaryDirectory(prefix=".execution-", dir=parent) as temp:
        pending = Path(temp) / "artifact"
        save_result(envelope, {}, pending)
        os.rename(pending, directory)
    return directory / "result.json"


def read_execution(path: Path) -> Execution:
    value = inspect_result(path)["envelope"]
    if (
        value["payload"]["arrays"]
        or value["result_kind"] != "experiment.manifest"
        or value["method"] != {"id": "soma.protocol.replay", "version": "1"}
    ):
        raise ProtocolError("Not a protocol execution artifact")
    return Execution.from_dict(value["payload"]["values"])


def history(paths: list[Path]) -> dict[str, Any]:
    records = [read_execution(p).record() for p in paths]
    studies = {r["protocol"]["protocol"]["id"] for r in records}
    if len(studies) > 1:
        raise ProtocolError("Independent studies cannot be pooled as one longitudinal history")
    ids = [r["execution_id"] for r in records]
    sequences = [r["sequence"] for r in records]
    if len(set(ids)) != len(ids) or len(set(sequences)) != len(sequences):
        raise ProtocolError("Duplicate history execution ID/sequence")
    return {
        "executions": sorted(records, key=lambda r: r["sequence"]),
        "ordering": "explicit run sequence, never filenames",
        "human_longitudinal_identity_verified": False,
    }


def append_history(execution: Execution, root: Path) -> Path:
    """Append an immutable run under an explicit study root; never overwrite a sequence."""
    import fcntl
    import stat

    root = safe_root(root, create=True)
    descriptor = os.open(root / ".history.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ProtocolError("Invalid history lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        records = [
            p / "result.json" for p in root.glob("execution-*") if (p / "result.json").is_file()
        ]
        previous = history(records)["executions"]
        current = execution.record()
        if previous:
            if current["protocol"]["protocol"]["id"] != previous[0]["protocol"]["protocol"]["id"]:
                raise ProtocolError("Execution belongs to a different study")
            if current["sequence"] <= max(r["sequence"] for r in previous):
                raise ProtocolError("Append-only history requires a new increasing sequence")
        return write_execution(execution, root / f"execution-{current['sequence']:06d}")
    finally:
        os.close(descriptor)
