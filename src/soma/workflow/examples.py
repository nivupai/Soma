"""Explicit synthetic DAG descriptions. Creating/inspecting one performs no science."""

import copy
from dataclasses import replace
from typing import Any

from soma.workflow.model import Artifact, Graph, Stage, WorkflowError
from soma.workflow.operations import builtins


def metadata(family: str, kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset_identity": "synthetic-workflow-" + family + "-v1",
        "subject_identity": None,
        "units": {"values": "1"},
        "spatial_reference": None,
        "temporal_reference": None,
        "estimand": "bounded synthetic demonstration; " + kind,
        "limitations": ["numerical example; no anatomical/statistical/clinical certification"],
        "restrictions": ["synthetic only; no participant inputs"],
    }
    if family == "eeg":
        result.update(
            fs_hz=160.0,
            reference="none",
            channels=["C3", "C4"],
            units={"voltage": "V"},
            temporal_reference={"fs_hz": 160.0},
        )
    else:
        result["spatial_reference"] = {"frame": "RAS", "space": "synthetic-native", "unit": "m"}
    if kind == "eeg.psd":
        result["units"] = {"density": "V^2/Hz", "frequency": "Hz"}
    if kind == "eeg.bands":
        result["units"] = {"power": "V^2"}
    if kind == "fmri.contrast":
        result["units"] = {"effect": "BOLD/regressor", "variance": "(BOLD/regressor)^2"}
    if kind == "mri.labels":
        result["ontology"] = {"0": "background", "1": "heuristic-foreground"}
    if family == "fmri":
        result.update(confirmatory_claim_allowed=False, temporal_reference={"tr_s": 2.0})
    return result


def example(family: str) -> Graph:
    descriptions: dict[str, list[tuple[str, dict[str, str], dict[str, Any]]]] = {
        "eeg": [
            ("generate", {}, {"fs_hz": 160.0, "duration_s": 4.0}),
            ("validate", {"recording": "generate-recording"}, {}),
            ("reference", {"validated": "validate-validated"}, {"reference": "average"}),
            ("psd", {"referenced": "reference-referenced"}, {"nperseg": 320, "noverlap": 160}),
            ("bands", {"psd": "psd-psd"}, {"mu": [8.0, 13.0], "beta": [13.0, 30.0]}),
        ],
        "mri": [
            ("generate", {}, {}),
            ("geometry", {"image": "generate-image"}, {}),
            (
                "preprocess",
                {"validated": "geometry-validated"},
                {
                    "n4": {"enabled": True, "iterations": [1], "shrink_factor": 1},
                    "resampling": {"enabled": False},
                },
            ),
            ("segment", {"processed": "preprocess-processed"}, {"threshold": 1.0}),
            ("qc", {"labels": "segment-labels", "processed": "preprocess-processed"}, {}),
            ("surface", {"labels": "segment-labels"}, {}),
        ],
        "fmri": [
            ("generate", {}, {"n_scans": 40}),
            ("validate", {"bold": "generate-bold"}, {}),
            ("design", {"validated": "validate-validated"}, {}),
            ("fit", {"validated": "validate-validated", "design": "design-design"}, {}),
            (
                "contrast",
                {"fit": "fit-fit"},
                {"weights": {"task": 1.0}, "confirmatory_claim_allowed": False},
            ),
            ("roi", {"contrast": "contrast-contrast"}, {}),
        ],
        "source": [
            ("geometry", {}, {}),
            ("forward", {"geometry": "geometry-geometry"}, {"scale": 1.0}),
            ("inverse", {"forward": "forward-forward"}, {"lambda2": 0.1}),
            ("reconstruct", {"forward": "forward-forward", "inverse": "inverse-inverse"}, {}),
        ],
    }
    if family not in descriptions:
        raise WorkflowError("Supported examples: eeg, mri, fmri, source")
    registry = builtins()
    stages = []
    artifacts = []
    for name, inputs, params in descriptions[family]:
        op = registry.operations[family + "." + name]
        outputs = {port: name + "-" + port for port in op.outputs}
        stage = Stage(name, op.name, inputs, outputs, params, seed=18042 if op.stochastic else None)
        stages.append(stage)
        for port, node in outputs.items():
            meta = metadata(family, op.outputs[port])
            if family == "eeg" and name in {"reference", "psd", "bands"}:
                meta["reference"] = "average"
            artifacts.append(Artifact(node, op.outputs[port], meta, producer=name))
    graph = Graph("synthetic-" + family, tuple(artifacts), tuple(stages))
    registry.validate(graph)
    return graph


def changed(graph: Graph) -> Graph:
    """One predefined scientific change; no mutation of the original graph."""
    stages = []
    for s in graph.stages:
        p = copy.deepcopy(s.parameters)
        if s.implementation == "eeg.reference":
            p["reference"] = "none"
        elif s.implementation == "mri.segment":
            p["threshold"] = 1.2
        elif s.implementation == "fmri.contrast":
            p["weights"]["task"] = 2.0
        elif s.implementation == "source.forward":
            p["scale"] = 1.2
        stages.append(replace(s, parameters=p))
    artifacts = graph.artifacts
    if graph.id == "synthetic-eeg":
        artifacts = tuple(
            replace(a, metadata={**a.metadata, "reference": "none"})
            if a.producer in {"reference", "psd", "bands"}
            else a
            for a in artifacts
        )
    return replace(graph, stages=tuple(stages), artifacts=artifacts)
