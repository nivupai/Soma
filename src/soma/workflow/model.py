"""Typed bipartite workflow contracts, using the established pipeline ordering."""

import hashlib
import hmac
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from soma.pipeline.contracts import StageSpec, ordered_graph
from soma.results.contracts import UNITS, canonical


class WorkflowError(ValueError):
    """A workflow contract, identity, integrity or recovery decision failed."""


def digest(value: Any) -> str:
    """Version-1 typed canonical SHA-256; finite JSON types only, no coercion."""

    def typed(x: Any) -> Any:
        if x is None:
            return ["null"]
        if type(x) in (bool, int, float, str):
            return [type(x).__name__, x]
        if isinstance(x, list):
            return ["list", [typed(v) for v in x]]
        if isinstance(x, dict) and all(type(k) is str for k in x):
            return ["map", [[k, typed(x[k])] for k in sorted(x)]]
        raise WorkflowError("Canonical identity requires explicit finite JSON types")

    return hashlib.sha256(canonical(typed(value))).hexdigest()


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise WorkflowError("Invalid opaque graph identifier")


def relative(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("/", "."))
        or "\\" in value
        or ":" in value
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise WorkflowError("Only safe relative permitted references are accepted")


def opaque_subject(subject: str, *, secret: bytes) -> str:
    """Keyed pseudonym; keep the secret outside graphs and exports. Not anonymization."""
    if len(secret) < 32 or not subject:
        raise WorkflowError("Explicit private key of at least 32 bytes and subject required")
    return "subject-" + hmac.new(secret, subject.encode(), hashlib.sha256).hexdigest()


def scientific(metadata: dict[str, Any], kind: str) -> None:
    required = {
        "dataset_identity",
        "subject_identity",
        "units",
        "spatial_reference",
        "temporal_reference",
        "estimand",
        "limitations",
        "restrictions",
    }
    if not required <= metadata.keys() or not metadata["dataset_identity"]:
        raise WorkflowError("Scientific metadata incomplete: reuse is INDETERMINATE")
    subject = metadata["subject_identity"]
    if subject is not None and (
        not isinstance(subject, str) or not re.fullmatch(r"subject-[a-f0-9]{64}", subject)
    ):
        raise WorkflowError("Only keyed opaque subject identities are permitted")
    if (
        not isinstance(metadata["units"], dict)
        or not metadata["estimand"]
        or any(unit not in UNITS for unit in metadata["units"].values())
    ):
        raise WorkflowError("Explicit units and estimand required")
    for key in ["limitations", "restrictions"]:
        if not isinstance(metadata[key], list) or not all(
            isinstance(x, str) for x in metadata[key]
        ):
            raise WorkflowError("Explicit limitation/restriction lists required")
    if kind.startswith(("mri.", "source.", "fmri.")):
        space = metadata["spatial_reference"]
        if not isinstance(space, dict) or not {"frame", "space", "unit"} <= space.keys():
            raise WorkflowError("Explicit spatial reference required")
        if space["frame"] not in {"RAS", "LPS", "HEAD", "MRI", "TEMPLATE_MRI"} or (
            space["unit"] not in {"m", "mm"}
        ):
            raise WorkflowError("Unsupported spatial reference")
    if kind.startswith("eeg.") and not {"fs_hz", "reference", "channels"} <= metadata.keys():
        raise WorkflowError("EEG sampling/reference/channels missing")
    if kind.startswith("eeg.") and (metadata["fs_hz"] <= 0 or not metadata["channels"]):
        raise WorkflowError("Invalid EEG sampling/channel declaration")
    if kind.startswith("mri.labels") and not metadata.get("ontology"):
        raise WorkflowError("Explicit segmentation ontology required")
    if kind.startswith("fmri.") and metadata.get("confirmatory_claim_allowed") is not False:
        raise WorkflowError("Workflow fMRI is descriptive only")
    digest(metadata)


@dataclass(frozen=True)
class Artifact:
    id: str
    kind: str
    metadata: dict[str, Any]
    producer: str | None = None
    fingerprint: str | None = None
    reference: str | None = None
    validation: str = "VALIDATED_NUMERICAL"


@dataclass(frozen=True)
class Stage:
    id: str
    implementation: str
    inputs: dict[str, str]
    outputs: dict[str, str]
    parameters: dict[str, Any] = field(default_factory=dict)
    algorithm_version: str = "1"
    seed: int | None = None
    stream: str = "numpy.PCG64-v1"
    precision: str = "native-explicit"
    execution: dict[str, Any] = field(default_factory=lambda: {"workers": 1, "threads": 1})


@dataclass(frozen=True)
class Graph:
    id: str
    artifacts: tuple[Artifact, ...]
    stages: tuple[Stage, ...]
    schema: str = "soma.workflow/1.0.0"
    presentation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["artifacts"], value["stages"] = list(value["artifacts"]), list(value["stages"])
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Graph":
        try:
            return cls(
                **{
                    **value,
                    "artifacts": tuple(Artifact(**a) for a in value["artifacts"]),
                    "stages": tuple(Stage(**s) for s in value["stages"]),
                }
            )
        except (TypeError, KeyError) as error:
            raise WorkflowError("Invalid closed workflow description") from error

    def order(self) -> list[Stage]:
        try:
            return self._order()
        except WorkflowError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            raise WorkflowError("Invalid typed graph or scientific metadata") from error

    def _order(self) -> list[Stage]:
        if self.schema != "soma.workflow/1.0.0":
            raise WorkflowError("Unsupported workflow version")
        identifier(self.id)
        all_nodes: list[Artifact | Stage] = [*self.artifacts, *self.stages]
        if len(all_nodes) > 5000 or len({n.id for n in all_nodes}) != len(all_nodes):
            raise WorkflowError("Duplicate node IDs or graph exceeds 5000-node bound")
        for n in all_nodes:
            identifier(n.id)
        artifacts = {a.id: a for a in self.artifacts}
        stages = {s.id: s for s in self.stages}
        if sum(len(s.inputs) + len(s.outputs) for s in self.stages) > 20000:
            raise WorkflowError("Graph edge bound exceeded")
        for a in self.artifacts:
            scientific(a.metadata, a.kind)
            if a.validation != "VALIDATED_NUMERICAL":
                raise WorkflowError("Artifact validation is INDETERMINATE or failed")
            if a.producer is None:
                if not a.fingerprint or not re.fullmatch("[a-f0-9]{64}", a.fingerprint):
                    raise WorkflowError("Input content fingerprint required")
                if a.reference is not None:
                    relative(a.reference)
            elif a.producer not in stages or a.id not in stages[a.producer].outputs.values():
                raise WorkflowError("Unresolvable or inconsistent producer")
            elif a.reference is not None or a.fingerprint is not None:
                raise WorkflowError("Derived artifacts cannot override producer identity")
        seen: set[str] = set()
        specs = []
        for s in sorted(self.stages, key=lambda s: s.id):
            if not s.outputs or not isinstance(s.inputs, dict) or not isinstance(s.outputs, dict):
                raise WorkflowError("Explicit stage ports required")
            if (
                set(s.inputs.values()) - artifacts.keys()
                or set(s.outputs.values()) - artifacts.keys()
            ):
                raise WorkflowError("Missing artifact dependency")
            if len(set(s.outputs.values())) != len(s.outputs) or seen & set(s.outputs.values()):
                raise WorkflowError("Duplicate output producers")
            seen.update(s.outputs.values())
            if any(artifacts[a].producer != s.id for a in s.outputs.values()):
                raise WorkflowError("Output producer identity inconsistent")
            if s.execution != {"workers": 1, "threads": 1} or s.precision != "native-explicit":
                raise WorkflowError("Only bounded serial native-explicit execution supported")
            if s.seed is not None and (type(s.seed) is not int or not 0 <= s.seed < 2**32):
                raise WorkflowError("Explicit uint32 seed required")
            if s.stream != "numpy.PCG64-v1":
                raise WorkflowError("Unsupported random stream")
            digest(s.parameters)
            deps = tuple(
                sorted(
                    {
                        str(artifacts[a].producer)
                        for a in s.inputs.values()
                        if artifacts[a].producer is not None
                    }
                )
            )
            specs.append(
                StageSpec(
                    s.id,
                    deps,
                    {n: artifacts[n].kind for n in s.inputs.values()},
                    {n: artifacts[n].kind for n in s.outputs.values()},
                )
            )
        try:
            return [
                stages[s.name]
                for s in ordered_graph(specs, {a.id for a in self.artifacts if a.producer is None})
            ]
        except ValueError as error:
            raise WorkflowError(str(error)) from error

    def edges(self) -> list[tuple[str, str]]:
        return [(a, s.id) for s in self.stages for a in s.inputs.values()] + [
            (s.id, a) for s in self.stages for a in s.outputs.values()
        ]

    def lineage(self, node: str, *, downstream: bool = False) -> dict[str, Any]:
        self.order()
        if node not in ({a.id for a in self.artifacts} | {s.id for s in self.stages}):
            raise WorkflowError("Unknown lineage node")
        adjacency: dict[str, list[str]] = {}
        for a, b in self.edges():
            left, right = (a, b) if downstream else (b, a)
            adjacency.setdefault(left, []).append(right)
        found = {node}
        todo = [node]
        while todo:
            for other in adjacency.get(todo.pop(), []):
                if other not in found:
                    found.add(other)
                    todo.append(other)
        return {
            "node": node,
            "direction": "downstream" if downstream else "upstream",
            "nodes": sorted(found),
            "edges": [[a, b] for a, b in self.edges() if a in found and b in found],
        }


def invalidation(before: Graph, after: Graph) -> dict[str, Any]:
    before.order()
    after.order()
    old = {n.id: asdict(n) for n in list[Artifact | Stage]([*before.artifacts, *before.stages])}
    new = {n.id: asdict(n) for n in list[Artifact | Stage]([*after.artifacts, *after.stages])}
    changed = sorted(n for n in old.keys() | new.keys() if old.get(n) != new.get(n))
    reasons = {}
    affected: set[str] = set()
    for node in changed:
        descendants = after.lineage(node, downstream=True)["nodes"] if node in new else [node]
        affected.update(descendants)
        reasons[node] = {
            "reason": "added/removed/changed computational declaration",
            "fields": [
                k
                for k in (old.get(node, {}).keys() | new.get(node, {}).keys())
                if old.get(node, {}).get(k) != new.get(node, {}).get(k)
            ],
            "invalidated": descendants,
        }
    return {
        "changed": changed,
        "invalidated": sorted(affected),
        "reasons": reasons,
        "presentation_excluded": True,
    }
