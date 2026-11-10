"""Protocol requirements bind existing allowlisted workflow methods, without estimators."""

import copy
import json
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Any

import numpy as np
from packaging.specifiers import SpecifierSet

from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit
from soma.fmri.inference import InferencePolicy
from soma.protocol.model import Protocol, ProtocolError, anatomy, methods
from soma.workflow.examples import example as workflow_example
from soma.workflow.model import Artifact, Graph, Stage, digest, identifier
from soma.workflow.operations import builtins, functional
from soma.workflow.runtime import Operation, Registry


def fmri_model(
    inputs: dict[str, Any], parameters: dict[str, Any], seed: int | None
) -> dict[str, Any]:
    config = ModelConfig(
        hrf_model=parameters["hrf_model"],
        noise_model=parameters["noise_model"],
        drift_model=parameters["drift_model"],
        confound_columns=tuple(parameters["confound_columns"]),
    )
    run = functional(inputs["validated"])
    if parameters["confirmatory_claim_allowed"] is not False:
        raise ProtocolError("Replay cannot grant confirmation")
    estimate = contrast(
        fit(run, config),
        Contrast(parameters["contrast"]["name"], parameters["contrast"]["weights"]),
        policy=InferencePolicy(mode="descriptive", correction=parameters["correction"]),
    )
    mask = run.mask.array().astype(bool)
    return {
        "contrast": {
            "effect": np.asarray(estimate.maps["effect_size"].dataobj)[mask],
            "variance": np.asarray(estimate.maps["effect_variance"].dataobj)[mask],
            "confirmatory_claim_allowed": False,
            "hrf_model": config.hrf_model,
            "noise_model": config.noise_model,
            "correction": parameters["correction"],
            "policy": estimate.metadata["inference_policy"],
        }
    }


def registry() -> Registry:
    operations = list(builtins().operations.values())
    operations.append(
        Operation(
            "protocol.fmri.model",
            {"validated": "fmri.validated"},
            {"contrast": "fmri.contrast"},
            fmri_model,
        )
    )
    return Registry(operations)


def projection(graph: Graph) -> dict[str, Any]:
    r = registry()
    r.validate(graph)
    stages = {}
    for stage in graph.stages:
        value = asdict(stage)
        value.pop("id")
        if r.operations[stage.implementation].stochastic:
            value["seed"] = "$SCHEDULED"
        stages[stage.id] = {"requirement_id": "method-" + stage.id, **value}
    artifacts = {}
    for artifact in graph.artifacts:
        value = asdict(artifact)
        value.pop("id")
        value["metadata"].pop("dataset_identity")
        value["metadata"].pop("subject_identity")
        artifacts[artifact.id] = value
    return {"stages": stages, "artifacts": artifacts}


def base_graph(family: str) -> Graph:
    g = workflow_example(family)
    if family != "fmri":
        return g
    keep_stages = tuple(s for s in g.stages if s.id not in {"design", "fit", "contrast"})
    model = Stage(
        "model",
        "protocol.fmri.model",
        {"validated": "validate-validated"},
        {"contrast": "contrast-contrast"},
        {
            "hrf_model": "spm",
            "noise_model": "ols",
            "drift_model": None,
            "confound_columns": ["motion", "trend"],
            "contrast": {"name": "task", "weights": {"task": 1.0}},
            "correction": "bh",
            "confirmatory_claim_allowed": False,
        },
    )
    artifacts = tuple(a for a in g.artifacts if a.producer not in {"design", "fit"})
    artifacts = tuple(
        Artifact(
            a.id,
            a.kind,
            a.metadata,
            producer="model" if a.id == "contrast-contrast" else a.producer,
        )
        for a in artifacts
    )
    return Graph(g.id, artifacts, (*keep_stages, model))


def example_protocol(family: str) -> Protocol:
    graph = base_graph(family)
    requirements = projection(graph)
    policy = json.loads(
        files("soma.resources").joinpath("workflow-tolerances-v1.json").read_text()
    )[family]
    axes = {
        "eeg": ["C3.mu", "C4.mu", "C3.beta", "C4.beta"],
        "mri": ["background_m3", "foreground_m3"],
        "fmri": ["mean_effect", "mean_variance"],
        "source": [
            "estimate0",
            "estimate1",
            "estimate2",
            "resolution0",
            "resolution1",
            "resolution2",
        ],
    }[family]
    units = {
        "eeg": ["V^2"] * 4,
        "mri": ["m^3"] * 2,
        "fmri": ["BOLD/regressor", "(BOLD/regressor)^2"],
        "source": ["1"] * 6,
    }[family]
    preprocessing = {
        n: s["parameters"]
        for n, s in requirements["stages"].items()
        if s["implementation"] in {"eeg.reference", "mri.preprocess"}
    }
    document = {
        "schema": "soma.protocol/1.0.0",
        "id": "synthetic-" + family + "-research",
        "name": "Controlled synthetic " + family + " protocol",
        "version": "1.0.0",
        "scientific": {
            "question": "Are declared "
            + family
            + " numerical outcomes stable under permitted replay?",
            "objective": "Descriptive synthetic numerical validation, not human replication",
            "estimand": (
                "Per-realization selected numerical summaries; no pooled-trial or human inference"
            ),
            "population": {
                "unit": "synthetic-realization",
                "dataset_namespace": graph.artifacts[0].metadata["dataset_identity"],
                "scope": "explicit bounded synthetic generators only",
                "inclusion": [
                    "all prespecified realizations, independently seeded where stochastic"
                ],
                "exclusion": [
                    "retain missing/invalid realizations as deviations, never favorable selection"
                ],
            },
            "conditions": ["fixed known synthetic acquisition and declared model"],
            "preprocessing": preprocessing,
            "analysis_methods": methods(requirements),
            "primary_outcomes": axes,
            "inference": {
                "mode": "descriptive",
                "confirmatory_claim_allowed": False,
                "correction": "bh" if family == "fmri" else "none",
                "assumptions": [
                    "selected numerical summaries are not statistical significance tests"
                ],
            },
            "sensitivity_analyses": [],
            "qc": {
                "required_stages": list(requirements["stages"]),
                "missing_policy": "retain_all_units_and_report",
                "exclusion_policy": "prespecified_non_outcome_only",
            },
            "anatomical_conventions": anatomy(requirements),
            "source_conductivity": None,
            "limitations": [
                (
                    "synthetic only; no biological drift, human reliability "
                    "or anatomical certification"
                ),
                "dimensionless source toy has no conductivity physics"
                if family == "source"
                else "MRI foreground is not tissue truth"
                if family == "mri"
                else "descriptive outcomes only",
            ],
        },
        "requirements": requirements,
        "replay_policy": {
            "controlled_axes": [
                "snapshot",
                "added_units",
                "session",
                "environment",
                "editorial_revision",
            ],
            "platforms": [
                {"system": os, "machine": arch, "python": py}
                for os, arch in [("Darwin", "arm64"), ("Linux", "x86_64")]
                for py in ["3.11", "3.12"]
            ],
            "software_ranges": {
                "numpy": ">=2.1,<3",
                "scipy": ">=1.14,<2",
                "nilearn": ">=0.14,<0.15",
                "pandas": ">=2.3,<3",
                "mne": ">=1.13,<2",
                "SimpleITK": ">=2.4,<3",
            },
            "seed_schedule": {"algorithm": "sha256-unit-session-v1", "master_seed": 19042},
            "synthetic_only": True,
        },
        "tolerances": {
            **policy,
            "axes": axes,
            "units": units,
            "missing_policy": "indeterminate",
            "scope": "selected_numerical_summaries",
        },
    }
    return Protocol.from_dict(document)


@dataclass(frozen=True)
class Snapshot:
    _canonical: bytes

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Snapshot":
        from soma.protocol.model import closed
        from soma.results.contracts import canonical

        try:
            closed(value, {"schema", "id", "namespace", "synthetic", "members", "restrictions"})
            if (
                value["schema"] != "soma.dataset.snapshot/1.0.0"
                or type(value["synthetic"]) is not bool
            ):
                raise ProtocolError("Unsupported snapshot schema")
            identifier(value["id"])
            if (
                not value["namespace"]
                or not value["restrictions"]
                or not 1 <= len(value["members"]) <= 64
            ):
                raise ProtocolError(
                    "Explicit bounded snapshot, permissions and membership required"
                )
            identities = []
            for member in value["members"]:
                closed(member, {"unit_id", "session", "available", "reason"})
                identifier(member["unit_id"])
                identifier(member["session"])
                if type(member["available"]) is not bool or member["reason"] != (
                    None if member["available"] else "INPUT_MISSING"
                ):
                    raise ProtocolError("Missing inputs require explicit non-outcome reason")
                identities.append((member["unit_id"], member["session"]))
            if len(set(identities)) != len(identities):
                raise ProtocolError("Duplicate sampling unit/session")
            return cls(canonical(value))
        except ProtocolError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise ProtocolError("Invalid snapshot declaration") from error

    def document(self) -> dict[str, Any]:
        value = json.loads(self._canonical)
        Snapshot.from_dict(value)
        return dict(value)

    @property
    def fingerprint(self) -> str:
        return digest(self.document())


def example_snapshot(
    protocol: Protocol, *, count: int = 1, identity: str = "snapshot-1", session: str = "session-1"
) -> Snapshot:
    return Snapshot.from_dict(
        {
            "schema": "soma.dataset.snapshot/1.0.0",
            "id": identity,
            "namespace": protocol.document()["scientific"]["population"]["dataset_namespace"],
            "synthetic": True,
            "members": [
                {
                    "unit_id": f"realization-{n + 1:03d}",
                    "session": session,
                    "available": True,
                    "reason": None,
                }
                for n in range(count)
            ],
            "restrictions": ["synthetic only; no participant measurements"],
        }
    )


def seed_for(protocol: Protocol, unit: str, session: str) -> int:
    p = protocol.document()
    return int(
        digest(
            {
                "protocol_id": p["id"],
                "unit": unit,
                "session": session,
                "schedule": p["replay_policy"]["seed_schedule"],
            }
        )[:8],
        16,
    )


def graph_for(protocol: Protocol, snapshot: Snapshot, member: dict[str, Any]) -> Graph:
    p = protocol.document()
    s = snapshot.document()
    if not s["synthetic"] or p["scientific"]["population"]["unit"] != "synthetic-realization":
        raise ProtocolError(
            "Human identity/session/permission evidence is not implemented; replay INDETERMINATE"
        )
    population = p["scientific"]["population"]
    if (
        population["scope"] != "explicit bounded synthetic generators only"
        or population["inclusion"]
        != ["all prespecified realizations, independently seeded where stochastic"]
        or population["exclusion"]
        != ["retain missing/invalid realizations as deviations, never favorable selection"]
    ):
        raise ProtocolError("Eligibility policy has no executable adapter; INDETERMINATE")
    if s["namespace"] != p["scientific"]["population"]["dataset_namespace"]:
        raise ProtocolError("Dataset namespace outside frozen population scope")
    if member not in s["members"]:
        raise ProtocolError("Unscheduled sampling unit")
    stages = []
    for n, req in p["requirements"]["stages"].items():
        d = copy.deepcopy(req)
        d.pop("requirement_id")
        if d["seed"] == "$SCHEDULED":
            d["seed"] = seed_for(protocol, member["unit_id"], member["session"])
        stages.append(Stage(id=n, **d))
    artifacts = []
    for n, req in p["requirements"]["artifacts"].items():
        d = copy.deepcopy(req)
        d["metadata"].update(dataset_identity=s["namespace"], subject_identity=None)
        artifacts.append(Artifact(id=n, **d))
    g = Graph(
        "bound-"
        + digest({"protocol": p["id"], "unit": member["unit_id"], "session": member["session"]})[
            :24
        ],
        tuple(artifacts),
        tuple(stages),
    )
    registry().validate(g)
    return g


def conformance(
    protocol: Protocol,
    graph: Graph,
    *,
    snapshot: Snapshot | None = None,
    member: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deviations = []
    p = protocol.document()

    def deviation(
        category: str, stage: str, expected: Any, observed: Any, consequence: str
    ) -> None:
        deviations.append(
            {
                "category": category,
                "stage": stage,
                "original_policy": expected,
                "observed_behavior": observed,
                "evidence": "structural protocol-to-workflow comparison",
                "scientific_consequence": consequence,
                "resolution_status": "UNAPPROVED",
                "authorized_amendment_reference": None,
            }
        )

    try:
        expected_axes = None
        if "bands" in p["requirements"]["stages"]:
            expected_axes = ["C3.mu", "C4.mu", "C3.beta", "C4.beta"]
        elif "qc" in p["requirements"]["stages"]:
            expected_axes = ["background_m3", "foreground_m3"]
        elif "roi" in p["requirements"]["stages"]:
            expected_axes = ["mean_effect", "mean_variance"]
        elif "reconstruct" in p["requirements"]["stages"]:
            expected_axes = [
                "estimate0",
                "estimate1",
                "estimate2",
                "resolution0",
                "resolution1",
                "resolution2",
            ]
        if (
            expected_axes != p["tolerances"]["axes"]
            or p["scientific"]["primary_outcomes"] != expected_axes
        ):
            deviation(
                "OUTCOME_CONTRACT_MISMATCH",
                "outcomes",
                expected_axes,
                p["tolerances"]["axes"],
                "unimplemented or mislabeled outcome selector",
            )
        actual = projection(graph)
        for section in ["stages", "artifacts"]:
            for n in sorted(p["requirements"][section].keys() | actual[section].keys()):
                if p["requirements"][section].get(n) != actual[section].get(n):
                    deviation(
                        "METHOD_OR_METADATA_MISMATCH",
                        n,
                        p["requirements"][section].get(n),
                        actual[section].get(n),
                        "incompatible scientific computation",
                    )
        if p["scientific"]["source_conductivity"] is not None:
            deviation(
                "UNSUPPORTED_FORWARD_SPECIFICATION",
                "forward",
                None,
                p["scientific"]["source_conductivity"],
                "dimensionless toy cannot implement conductivity/anatomical claims",
            )
        for stage in graph.stages:
            if stage.implementation == "protocol.fmri.model":
                req = stage.parameters
                if (
                    set(req)
                    != {
                        "hrf_model",
                        "noise_model",
                        "drift_model",
                        "confound_columns",
                        "contrast",
                        "correction",
                        "confirmatory_claim_allowed",
                    }
                    or req["confirmatory_claim_allowed"] is not False
                ):
                    raise ProtocolError("Unsupported inference override")
                ModelConfig(
                    hrf_model=req["hrf_model"],
                    noise_model=req["noise_model"],
                    drift_model=req["drift_model"],
                    confound_columns=tuple(req["confound_columns"]),
                )
                Contrast(req["contrast"]["name"], req["contrast"]["weights"])
                if req["correction"] != p["scientific"]["inference"]["correction"]:
                    raise ProtocolError("Correction differs from scientific inference policy")
        if snapshot is not None and member is not None:
            if graph.to_dict() != graph_for(protocol, snapshot, member).to_dict():
                deviation(
                    "UNAUTHORIZED_EXECUTION_OVERRIDE",
                    "workflow",
                    "sealed graph plus scheduled seed",
                    "observed graph differs",
                    "execution cannot be compliant",
                )
    except (ValueError, TypeError, KeyError) as error:
        deviation(
            "INVALID_OR_UNVERIFIABLE_WORKFLOW",
            "workflow",
            "valid registered stage contracts",
            type(error).__name__,
            "execution blocked",
        )
    return {
        "status": "CONFORMANT" if not deviations else "NONCONFORMANT",
        "deviations": deviations,
        "required_requirements": len(p["requirements"]["stages"]),
        "confirmatory_replication_authorized": False,
    }


def environment_permitted(protocol: Protocol, env: dict[str, Any]) -> bool:
    p = protocol.document()["replay_policy"]
    platform = {
        "system": env.get("system"),
        "machine": env.get("machine"),
        "python": str(env.get("python", ""))[:4],
    }
    if platform not in p["platforms"]:
        return False
    try:
        return all(
            env["libraries"][n] in SpecifierSet(spec) for n, spec in p["software_ranges"].items()
        )
    except (KeyError, ValueError, TypeError):
        return False
