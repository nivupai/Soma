"""Registered human pilots over M18 DAGs and M19 declarations; no new estimator."""

import copy
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.human.adapters import Selection
from soma.human.model import Identity, now, validate_cohort
from soma.human.permissions import PermissionEvidence, check_permission
from soma.protocol.binding import environment_permitted, example_protocol
from soma.protocol.model import Protocol, SealedProtocol, anatomy, methods, seal
from soma.results.contracts import canonical, create_result
from soma.results.io import inspect_result, save_result
from soma.workflow.model import Artifact, Graph, Stage, digest
from soma.workflow.runtime import Executor, Operation, Registry, content


def parameters(dataset: str) -> dict[str, Any]:
    if dataset == "eegmmidb":
        from soma.eeg.motor_imagery import MotorImageryConfig

        return {
            "method": "existing-motor-imagery-v2",
            "configuration": json.loads(canonical(asdict(MotorImageryConfig(plots=False)))),
        }
    if dataset == "ds000114":
        return {"method": "blocked-human-fmri-no-audited-derivatives"}
    return {
        "method": "existing-M10-multiotsu-M11-scoring",
        "threshold_tuning": False,
        "ontology": {"1": "CSF", "2": "GM", "3": "WM"},
        "prediction_input": "T1-intensity-only",
    }


def calculate(inputs: dict[str, Any], params: dict[str, Any], seed: int | None) -> dict[str, Any]:
    c = inputs["selection"]
    person = Identity.from_dict(c["identity"])
    d = person.document()
    permission = PermissionEvidence.from_dict(c["permission"])
    source = Path(c["permission_source"]).read_bytes()
    decision = check_permission(
        permission,
        dataset=d["dataset"],
        version=d["version"],
        purpose="methods_research",
        action="analyze",
        source_content=source,
    )
    if not decision["allowed"]:
        raise ValueError("Permission evidence no longer supports analysis")
    for role, path in c["files"].items():
        resource = Path(path).resolve(strict=True)
        if (
            not resource.is_relative_to(Path(c["root"]).resolve())
            or sha256(resource) != c["hashes"][role]
        ):
            raise ValueError("Changed or escaped human input")
    if params != parameters(d["dataset"]):
        raise ValueError("Unsupported scientific override")
    if d["dataset"] == "eegmmidb":
        from soma.datasets.eegbci import load_recording, recording_path
        from soma.eeg.motor_imagery import MotorImageryConfig, analyze_run

        expected_recording = recording_path(Path(c["root"]), int(c["raw_subject"]), int(d["run"]))
        if expected_recording.resolve() != Path(c["files"]["image"]).resolve():
            raise ValueError("Participant/run source mapping mismatch")
        raw, _ = load_recording(Path(c["root"]), int(c["raw_subject"]), int(d["run"]))
        try:
            result = analyze_run(
                raw,
                int(c["raw_subject"]),
                int(d["run"]),
                d["subject"],
                MotorImageryConfig(plots=False),
            )
        finally:
            raw.close()
        features = result["features"]
        values = {
            b: float(features.loc[features.band == b, "absolute_power_v2"].mean())
            for b in ["mu", "beta"]
        }
        return {
            "summary": {
                "values": values,
                "units": {"mu": "V^2", "beta": "V^2"},
                "qc": result["quality"]["trial_counts"],
                "sampling_unit": "subject",
                "inference": "descriptive-only; accepted trials do not become participants",
            }
        }
    if d["dataset"] in {"ibsr-v2", "mrbrains13"}:
        from soma.datasets.external_anatomy import TISSUES
        from soma.datasets.human_mri import align_t1, load_human, mapped_reference
        from soma.sdk.imaging import LabelVolume, score
        from soma.validation.human_tissues import predict_t1

        native_id = d["dataset"] + ":" + c["raw_subject"]
        image = load_human(
            Path(c["files"]["image"]), dataset=d["dataset"], subject=native_id, role="intensity"
        )
        native = load_human(
            Path(c["files"]["reference"]), dataset=d["dataset"], subject=native_id, role="labels"
        )
        image, alignment = align_t1(image, native, dataset=d["dataset"])
        prediction = predict_t1(image)
        reference, valid = mapped_reference(native, d["dataset"])
        reference_lv = LabelVolume(
            reference,
            native_id,
            image.metadata["space"],
            TISSUES,
            {"source": "independent provided manual labels; not prediction input"},
        )
        metrics = score(
            prediction, reference_lv, valid_mask=valid if d["dataset"] == "mrbrains13" else None
        )
        from soma.workflow.privacy import redact_export

        metrics = redact_export(json.loads(canonical(metrics)))
        return {
            "summary": {
                "values": metrics,
                "alignment": alignment,
                "truth_used_for_prediction": False,
                "sampling_unit": "subject",
                "inference": "descriptive-only tissue benchmark; not conductor validation",
            }
        }
    raise ValueError("No authorized scientific operation registered for this dataset")


def registry() -> Registry:
    return Registry(
        [
            Operation(
                "human.bound-pilot",
                {"selection": "human.selection"},
                {"summary": "human.summary"},
                calculate,
            )
        ]
    )


def metadata(dataset: str) -> dict[str, Any]:
    return {
        "dataset_identity": dataset,
        "subject_identity": None,
        "units": {"power": "V^2"}
        if dataset == "eegmmidb"
        else {"score": "1", "distance": "mm", "volume": "mm^3"},
        "spatial_reference": None,
        "temporal_reference": None,
        "estimand": "prespecified per-subject descriptive summaries",
        "limitations": [
            "identity/access do not establish statistical, anatomical or clinical validity"
        ],
        "restrictions": ["local participant records; no redistribution or confirmatory inference"],
    }


def template(dataset: str, version: str) -> Protocol:
    if dataset not in {"eegmmidb", "ibsr-v2", "mrbrains13", "ds000114"}:
        raise ValueError("Dataset has no registered human protocol adapter")
    d = example_protocol("eeg").document()
    d.update(id="human-" + dataset, name="Permission-aware " + dataset + " descriptive pilot")
    meta = metadata(dataset)
    graph = Graph(
        "human-pilot",
        (
            Artifact("selection", "human.selection", meta, fingerprint="0" * 64),
            Artifact("summary", "human.summary", meta, producer="analysis"),
        ),
        (
            Stage(
                "analysis",
                "human.bound-pilot",
                {"selection": "selection"},
                {"summary": "summary"},
                parameters(dataset),
            ),
        ),
    )
    requirements: dict[str, Any] = {"stages": {}, "artifacts": {}}
    for stage in graph.stages:
        value = asdict(stage)
        value.pop("id")
        value["requirement_id"] = "method-" + stage.id
        requirements["stages"][stage.id] = value
    for artifact in graph.artifacts:
        value = asdict(artifact)
        value.pop("id")
        value["metadata"].pop("dataset_identity")
        value["metadata"].pop("subject_identity")
        requirements["artifacts"][artifact.id] = value
    d["requirements"] = requirements
    s = d["scientific"]
    s.update(
        question=(
            "Are the selected cached records consistently identified and supported by use evidence?"
        ),
        objective="Bounded descriptive re-analysis; not independent prospective replication",
        estimand=meta["estimand"],
        population={
            "unit": "subject",
            "dataset_namespace": dataset,
            "scope": version,
            "inclusion": [
                (
                    "all explicitly selected records passing identity "
                    "and purpose-scoped permission checks"
                )
            ],
            "exclusion": [
                "retain every selected missing, ambiguous or unauthorized record with a reason"
            ],
        },
        conditions=[
            "unilateral motor imagery"
            if dataset == "eegmmidb"
            else "motor-task fMRI metadata audit"
            if dataset == "ds000114"
            else "structural T1 tissue benchmark"
        ],
        preprocessing={"analysis": parameters(dataset)},
        analysis_methods=methods(requirements),
        primary_outcomes=["mu", "beta"]
        if dataset == "eegmmidb"
        else ["metadata-readiness"]
        if dataset == "ds000114"
        else ["tissue_metrics"],
        anatomical_conventions=anatomy(requirements),
        qc={
            "required_stages": ["analysis"],
            "missing_policy": "retain_all_units_and_report",
            "exclusion_policy": "prespecified_non_outcome_only",
        },
        limitations=[
            "previously inspected human data; not a fresh holdout",
            "permission check is not legal authorization or individual consent verification",
            "descriptive only; no clinical or skull/scalp conductor validation",
        ],
    )
    d["replay_policy"]["synthetic_only"] = False
    d["tolerances"].update(
        axes=s["primary_outcomes"],
        units=["V^2", "V^2"] if dataset == "eegmmidb" else ["1"],
        atol=0.0,
        rtol=0.0,
    )
    return Protocol.from_dict(d)


def conformance(
    protocol: Protocol, selection: Selection, permission: PermissionEvidence, source: bytes | None
) -> dict[str, Any]:
    p = protocol.document()
    i = selection.identity.document()
    reasons = []
    expected = template(i["dataset"], i["version"])
    checked_science = copy.deepcopy(p["scientific"])
    checked_science["population"]["inclusion"] = checked_science["population"]["inclusion"][:1]
    if (
        checked_science != expected.document()["scientific"]
        or p["requirements"] != expected.document()["requirements"]
        or p["replay_policy"] != expected.document()["replay_policy"]
        or p["tolerances"] != expected.document()["tolerances"]
    ):
        reasons.append("unsupported scientific/eligibility/estimand/inference override")
    if p["id"] != expected.document()["id"]:
        reasons.append("study identifier mismatch")
    if i["dataset"] == "eegmmidb":
        acquisition = i["acquisition_metadata"]
        if (
            i["modality"] != "EEG"
            or acquisition.get("channels") != 64
            or acquisition.get("sfreq_hz") != 160.0
            or i["session"] is not None
            or i["temporal_reference"] != {"unit": "s", "fs_hz": 160.0}
        ):
            reasons.append(
                "EEG acquisition/reference/session declarations disagree with supported release"
            )
    if i["dataset"] in {"ibsr-v2", "mrbrains13"}:
        spatial = i["spatial_reference"] or {}
        if (
            i["modality"] != "MRI"
            or i["task"] != "structural"
            or i["session"] is not None
            or i["run"] is not None
            or spatial.get("frame") != "native-RAS"
        ):
            reasons.append("Anatomical acquisition/session/spatial declarations are incompatible")
    if i["availability"] != "AVAILABLE":
        reasons.append("input unavailable")
    if i["dataset"] == "eegmmidb" and (
        i["task"] != "unilateral-imagery" or i["run"] not in {"4", "8", "12"}
    ):
        reasons.append("motor execution/bilateral/baseline is not unilateral imagery")
    if i["dataset"] == "mrbrains13" and i["partition"] != "training":
        reasons.append("only labeled training subset is permitted")
    if i["modality"] == "fMRI" or i["dataset"] == "ds000114":
        reasons.append(
            "compatible audited preprocessing/transform evidence unavailable; human GLM blocked"
        )
    use = check_permission(
        permission,
        dataset=i["dataset"],
        version=i["version"],
        purpose="methods_research",
        action="analyze",
        source_content=source,
    )
    reasons.extend(use["reasons"])
    return {
        "status": "ELIGIBLE" if not reasons else "BLOCKED",
        "reasons": reasons,
        "permission": use,
        "sampling_unit": "subject",
        "confirmatory_claim_allowed": False,
    }


def graph_for(
    protocol: Protocol,
    selection: Selection,
    permission: PermissionEvidence,
    permission_source: Path,
) -> tuple[Graph, dict[str, Any]]:
    i = selection.identity.document()
    context = {
        "identity": i,
        "root": str(selection.root.resolve()),
        "raw_subject": selection.subject,
        "files": {k: str(p.resolve()) for k, p in selection.files},
        "hashes": dict(selection.hashes),
        "permission": permission.document(),
        "permission_source": str(permission_source.resolve()),
    }
    p = protocol.document()
    meta = metadata(i["dataset"])
    meta.update(
        subject_identity=i["subject"],
        dataset_identity=i["dataset"] + "@" + i["version"],
        human_identity=selection.identity.fingerprint,
        permission_context=permission.fingerprint,
        protocol_fingerprint=protocol.fingerprint,
    )
    g = Graph(
        "human-pilot",
        (
            Artifact("selection", "human.selection", meta, fingerprint=content(context)),
            Artifact("summary", "human.summary", meta, producer="analysis"),
        ),
        (
            Stage(
                "analysis",
                "human.bound-pilot",
                {"selection": "selection"},
                {"summary": "summary"},
                p["requirements"]["stages"]["analysis"]["parameters"],
            ),
        ),
    )
    registry().validate(g)
    return g, context


def plan(
    sealed: SealedProtocol,
    selections: list[Selection],
    permission: PermissionEvidence,
    permission_source: Path,
) -> dict[str, Any]:
    validate_cohort([s.identity for s in selections])
    inclusion = sealed.protocol.document()["scientific"]["population"]["inclusion"]
    if len(inclusion) != 2 or inclusion[1] != "frozen-cohort:" + cohort_key(
        [s.identity for s in selections]
    ):
        raise ValueError(
            "Frozen cohort membership/session/task/run mismatch; retain all scheduled units"
        )
    if len({s.identity.document()["dataset"] for s in selections}) != 1:
        raise ValueError("One dataset scope per human study")
    source = permission_source.read_bytes() if permission_source.is_file() else None
    units: list[dict[str, Any]] = []
    primary_hashes = []
    for s in selections:
        check = conformance(sealed.protocol, s, permission, source)
        try:
            s.verify_inputs()
        except (OSError, ValueError):
            check["status"] = "BLOCKED"
            check["reasons"].append("changed/missing/escaped source data")
        if "image" in dict(s.hashes):
            primary_hashes.append(dict(s.hashes)["image"])
        units.append(
            {
                "identity": s.identity.document(),
                "identity_fingerprint": s.identity.fingerprint,
                "input_hashes": dict(s.hashes),
                "facts": s.facts(),
                "eligibility": check,
                "planned_graph": graph_for(sealed.protocol, s, permission, permission_source)[
                    0
                ].to_dict(),
            }
        )
    if len(primary_hashes) != len(set(primary_hashes)):
        raise ValueError("Repeated recording content assigned to distinct identities")
    return {
        "schema": "soma.human.plan/1.0.0",
        "protocol": sealed.record(),
        "units": units,
        "status": "READY"
        if all(u["eligibility"]["status"] == "ELIGIBLE" for u in units)
        else "BLOCKED_OR_PARTIAL",
        "execution_started": False,
        "confirmation_authorized": False,
    }


def run(
    sealed: SealedProtocol,
    selections: list[Selection],
    permission: PermissionEvidence,
    permission_source: Path,
    *,
    cache: Path,
    output: Path,
    sequence: int,
) -> dict[str, Any]:
    from soma.datasets.human_mri import safe_local_output

    if "research_readiness" in sealed.protocol.document().get("optional_metadata", {}):
        raise ValueError(
            "Readiness protocols are read-only; legacy dispatch cannot bypass evidence gates"
        )
    safe_local_output(output)
    safe_local_output(cache)
    for selection in selections:
        source_root = selection.root.resolve(strict=True)
        if output.resolve().is_relative_to(source_root) or cache.resolve().is_relative_to(
            source_root
        ):
            raise ValueError("Human outputs and caches cannot modify an input dataset root")
    if type(sequence) is not int or sequence < 1:
        raise ValueError("Explicit positive sequence required")
    prepared = plan(sealed, selections, permission, permission_source)
    executor = Executor(registry(), cache)
    if not environment_permitted(sealed.protocol, executor.environment):
        raise ValueError("Unsupported software/build environment")
    started = now()
    units: list[dict[str, Any]] = copy.deepcopy(prepared["units"])
    for row, selection in zip(units, selections, strict=True):
        row["status"] = "BLOCKED"
        if row["eligibility"]["status"] != "ELIGIBLE":
            continue
        graph, context = graph_for(sealed.protocol, selection, permission, permission_source)
        # Private input mappings stay in memory; no stage returns them as outputs.
        selection.verify_inputs()
        workflow = executor.run(graph, inputs={"selection": context})
        from soma.workflow.privacy import redact_export

        row.update(
            status=workflow["status"],
            graph=graph.to_dict(),
            graph_identity=digest(graph.to_dict()),
            workflow=redact_export(workflow),
        )
        try:
            selection.verify_inputs()
        except (OSError, ValueError):
            row["status"] = "FAILED"
            row["eligibility"]["reasons"].append("source data changed during execution")
        if row["status"] == "COMPLETE":
            from soma.pipeline.cache import decode
            from soma.results.io import load_result
            from soma.workflow.runtime import identities

            keys = identities(graph, executor.registry, executor.environment)
            envelope, arrays = load_result(
                cache / keys["analysis"]["cache_key"] / "summary/result.json"
            )
            row["outcome"] = decode(envelope["payload"]["values"], arrays, {})
    record = {
        "schema": "soma.human.execution/1.0.0",
        "protocol": sealed.record(),
        "sequence": sequence,
        "started_at": started,
        "finished_at": now(),
        "units": units,
        "environment": executor.environment,
        "implementation_fingerprint": executor.registry.source,
        "permission": permission.document(),
        "interpretation": "DESCRIPTIVE_ONLY",
        "human_reliability_authorized": False,
        "status": "COMPLETE"
        if all(u["status"] == "COMPLETE" for u in units)
        else "BLOCKED_OR_PARTIAL",
    }
    record["record_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
    validate_execution(record)
    envelope = create_result(
        "experiment.manifest",
        {
            "computation": "permission-aware-human-pilot",
            "inputs": {},
            "environment": executor.environment,
            "assumptions": ["subject-level descriptive analysis"],
            "validation": {"identity": "recorded", "permissions": "purpose-scoped software policy"},
            "limitations": sealed.protocol.document()["scientific"]["limitations"],
        },
        values=record,
        provenance={"protocol_fingerprint": sealed.protocol.fingerprint},
        interpretation_state="DESCRIPTIVE_ONLY"
        if record["status"] == "COMPLETE"
        else "INDETERMINATE",
        method={"id": "soma.human.pilot", "version": "1"},
        parameters={},
        units={},
        dataset_identity=selections[0].identity.document()["dataset"],
        subject_identity=None,
        statistical_estimand=sealed.protocol.document()["scientific"]["estimand"],
    )
    save_result(envelope, {}, output)
    return record


def read_execution(path: Path) -> dict[str, Any]:
    envelope = inspect_result(path)["envelope"]
    if (
        envelope["method"] != {"id": "soma.human.pilot", "version": "1"}
        or envelope["payload"]["arrays"]
    ):
        raise ValueError("Not a metadata-only human execution")
    record = dict(envelope["payload"]["values"])
    expected = record.pop("record_sha256")
    if hashlib.sha256(canonical(record)).hexdigest() != expected:
        raise ValueError("Human record corruption")
    if (
        record["schema"] != "soma.human.execution/1.0.0"
        or record["interpretation"] != "DESCRIPTIVE_ONLY"
        or record["human_reliability_authorized"] is not False
    ):
        raise ValueError("Unsupported human interpretation")
    SealedProtocol(canonical(record["protocol"])).record()
    validate_cohort([Identity.from_dict(u["identity"]) for u in record["units"]])
    record["record_sha256"] = expected
    validate_execution(record)
    return record


def cohort_key(identities: list[Identity]) -> str:
    keys = [
        {
            k: i.document()[k]
            for k in [
                "dataset",
                "version",
                "subject",
                "session",
                "task",
                "run",
                "acquisition",
                "modality",
            ]
        }
        for i in identities
    ]
    return digest(sorted(keys, key=lambda x: canonical(x)))


def freeze_cohort(protocol: Protocol, identities: list[Identity]) -> SealedProtocol:
    validate_cohort(identities)
    d = protocol.document()
    if len(d["scientific"]["population"]["inclusion"]) != 1:
        raise ValueError("Cohort already frozen; create an explicit amendment")
    d["scientific"]["population"]["inclusion"].append("frozen-cohort:" + cohort_key(identities))
    return seal(Protocol.from_dict(d))


def compare(left: dict[str, Any], right: dict[str, Any], *, mode: str = "EXACT") -> dict[str, Any]:
    from soma.protocol.model import compare_protocols

    validate_execution(left)
    validate_execution(right)
    a = SealedProtocol(canonical(left["protocol"])).protocol
    b = SealedProtocol(canonical(right["protocol"])).protocol
    protocols = compare_protocols(a, b)
    if mode not in {"EXACT", "CONTROLLED", "EXPLORATORY"}:
        raise ValueError("Unknown human replay mode")
    reasons = []
    if mode == "EXPLORATORY":
        if not protocols["explicit_parent_amendment"] or not protocols["version_declaration_valid"]:
            reasons.append("explicit valid parent amendment required")
    elif protocols["scientific_change"]:
        reasons.append("scientific protocol differs")

    def key(unit: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            unit["identity"][k]
            for k in [
                "dataset",
                "version",
                "subject",
                "session",
                "task",
                "run",
                "acquisition",
                "modality",
            ]
        )

    ma = {key(u): u for u in left["units"]}
    mb = {key(u): u for u in right["units"]}
    if ma.keys() != mb.keys():
        reasons.append("subject/session/task alignment differs; no longitudinal alignment inferred")
    if left["permission"] != right["permission"]:
        reasons.append("authorization context differs")
    implementation_changed = (
        left["implementation_fingerprint"] != right["implementation_fingerprint"]
    )
    environment_changed = left["environment"] != right["environment"]
    if implementation_changed:
        reasons.append("implementation differs")
    if environment_changed and (
        mode == "EXACT" or "environment" not in a.document()["replay_policy"]["controlled_axes"]
    ):
        reasons.append("environment difference not authorized")
    incomplete = left["status"] != "COMPLETE" or right["status"] != "COMPLETE"
    if incomplete:
        reasons.append("missing or blocked scientific execution")
    inputs_changed = False
    outcome_changed = False
    for unit in ma.keys() & mb.keys():
        inputs_changed |= ma[unit]["input_hashes"] != mb[unit]["input_hashes"]
        outcome_changed |= ma[unit].get("outcome") != mb[unit].get("outcome")
        for field in ["spatial_reference", "temporal_reference", "acquisition_metadata"]:
            if ma[unit]["identity"][field] != mb[unit]["identity"][field]:
                reasons.append("acquisition/reference policy differs")
    numerical_applicable = (
        not inputs_changed
        and not protocols["scientific_change"]
        and not implementation_changed
        and not incomplete
        and ma.keys() == mb.keys()
    )
    if inputs_changed and (
        mode == "EXACT" or "snapshot" not in a.document()["replay_policy"]["controlled_axes"]
    ):
        reasons.append("observed input content differs")
    if outcome_changed and numerical_applicable:
        reasons.append("numerical outcome differs; frozen exact human policy")
    drift = [
        name
        for changed, name in [
            (inputs_changed, "DATA_DRIFT"),
            (protocols["scientific_change"], "PROTOCOL_DRIFT"),
            (implementation_changed, "IMPLEMENTATION_DRIFT"),
            (environment_changed, "EXECUTION_ENVIRONMENT_DRIFT"),
            (outcome_changed and numerical_applicable, "NUMERICAL_DRIFT"),
            (outcome_changed, "MEASUREMENT_OR_OUTCOME_DRIFT"),
            (incomplete, "MISSING_OR_UNVERIFIABLE_EVIDENCE"),
        ]
        if changed
    ]
    return {
        "schema": "soma.human.comparison/1.0.0",
        "authorized": not reasons,
        "mode": mode,
        "reasons": sorted(set(reasons)),
        "protocol_comparison": protocols,
        "drift": drift,
        "numerically_identical": not outcome_changed if numerical_applicable else None,
        "cache_interchangeability": False,
        "current_data_use_authorized": False,
        "comparison_scope": (
            "historical descriptive evidence; execution requires fresh permission checks"
        ),
        "confirmatory_replication_authorized": False,
        "human_longitudinal_reliability_established": False,
    }


def validate_execution(record: dict[str, Any]) -> None:
    from soma.human.model import checksum, timestamp
    from soma.protocol.model import closed

    closed(
        record,
        {
            "schema",
            "protocol",
            "sequence",
            "started_at",
            "finished_at",
            "units",
            "environment",
            "implementation_fingerprint",
            "permission",
            "interpretation",
            "human_reliability_authorized",
            "status",
            "record_sha256",
        },
    )
    expected = hashlib.sha256(
        canonical({k: v for k, v in record.items() if k != "record_sha256"})
    ).hexdigest()
    if expected != record["record_sha256"]:
        raise ValueError("Human record corruption")
    if (
        record["schema"] != "soma.human.execution/1.0.0"
        or record["interpretation"] != "DESCRIPTIVE_ONLY"
        or record["human_reliability_authorized"] is not False
    ):
        raise ValueError("Unsupported human interpretation")
    if (
        type(record["sequence"]) is not int
        or record["sequence"] < 1
        or timestamp(record["finished_at"]) < timestamp(record["started_at"])
    ):
        raise ValueError("Invalid run ordering/time")
    sealed = SealedProtocol(canonical(record["protocol"]))
    sealed.record()
    permission = PermissionEvidence.from_dict(record["permission"])
    checksum(record["implementation_fingerprint"])
    if not environment_permitted(sealed.protocol, record["environment"]):
        raise ValueError("Unsupported recorded environment")
    identities = [Identity.from_dict(u["identity"]) for u in record["units"]]
    validate_cohort(identities)
    inclusion = sealed.protocol.document()["scientific"]["population"]["inclusion"]
    if len(inclusion) != 2 or inclusion[1] != "frozen-cohort:" + cohort_key(identities):
        raise ValueError("Recorded frozen cohort differs")
    for unit, identity in zip(record["units"], identities, strict=True):
        if unit["identity_fingerprint"] != identity.fingerprint:
            raise ValueError("Identity fingerprint mismatch")
        for fingerprint in unit["input_hashes"].values():
            checksum(fingerprint)
        if unit["status"] not in {"COMPLETE", "BLOCKED", "FAILED", "CANCELLED"}:
            raise ValueError("Invalid unit completion status")
        if unit["status"] == "COMPLETE":
            if (
                unit["eligibility"]["status"] != "ELIGIBLE"
                or unit["workflow"]["status"] != "COMPLETE"
            ):
                raise ValueError("Incomplete unit claimed complete")
            graph = Graph.from_dict(unit["graph"])
            registry().validate(graph)
            if unit.get("graph_identity") != digest(graph.to_dict()):
                raise ValueError("Recorded graph identity mismatch")
            expected_parameters = sealed.protocol.document()["requirements"]["stages"]["analysis"][
                "parameters"
            ]
            if len(graph.stages) != 1 or graph.stages[0].parameters != expected_parameters:
                raise ValueError("Recorded method does not conform")
            for artifact in graph.artifacts:
                if (
                    artifact.metadata["subject_identity"] != identity.document()["subject"]
                    or artifact.metadata.get("permission_context") != permission.fingerprint
                ):
                    raise ValueError("Graph identity/permission context mismatch")
    complete = all(u["status"] == "COMPLETE" for u in record["units"])
    if record["status"] != ("COMPLETE" if complete else "BLOCKED_OR_PARTIAL"):
        raise ValueError("Invalid aggregate completion status")
