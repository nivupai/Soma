"""Adversarial graph contracts and precise scientific cache identities."""

import copy
from dataclasses import replace

import numpy as np
import pytest

from soma.sdk.workflow import (
    Executor,
    Graph,
    WorkflowError,
    builtins,
    changed,
    content,
    digest,
    example,
    identities,
    invalidation,
    opaque_subject,
    redact_export,
)


def modify(graph, section, index, **changes):
    value = graph.to_dict()
    value[section][index].update(changes)
    return Graph.from_dict(value)


def test_canonical_types_and_mapping_order():
    assert digest({"a": [1, 2.0], "b": True}) == digest({"b": True, "a": [1, 2.0]})
    assert len({digest(x) for x in [True, 1, 1.0, "1", [1], {"v": 1}]}) == 6
    for x in [float("nan"), float("inf"), np.int64(1), object(), (1,)]:
        with pytest.raises(ValueError):
            digest(x)
    assert content({"a": np.arange(3), "b": np.arange(4)}) == content(
        {"b": np.arange(4), "a": np.arange(3)}
    )


@pytest.mark.parametrize(
    "failure",
    [
        "cycle",
        "missing",
        "duplicate-stage",
        "duplicate-artifact",
        "producer",
        "type",
        "unknown-implementation",
        "version",
    ],
)
def test_invalid_graphs(failure):
    g = example("source")
    v = g.to_dict()
    if failure == "cycle":
        v["stages"][0]["inputs"] = {"geometry": "reconstruct-source"}
    elif failure == "missing":
        v["stages"][1]["inputs"]["geometry"] = "absent"
    elif failure == "duplicate-stage":
        v["stages"].append(copy.deepcopy(v["stages"][0]))
    elif failure == "duplicate-artifact":
        v["artifacts"].append(copy.deepcopy(v["artifacts"][0]))
    elif failure == "producer":
        v["artifacts"][0]["producer"] = "forward"
    elif failure == "type":
        v["artifacts"][0]["kind"] = "source.wrong"
    elif failure == "unknown-implementation":
        v["stages"][0]["implementation"] = "os.system"
    else:
        v["stages"][0]["algorithm_version"] = "99"
    with pytest.raises(WorkflowError):
        builtins().validate(Graph.from_dict(v))


@pytest.mark.parametrize(
    "field,value",
    [
        ("validation", "INDETERMINATE"),
        ("metadata", {}),
        ("id", "../escape"),
        ("producer", "missing"),
    ],
)
def test_unsafe_or_indeterminate_artifacts(field, value):
    g = modify(example("mri"), "artifacts", 0, **{field: value})
    with pytest.raises(WorkflowError):
        builtins().validate(g)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", None),
        ("seed", True),
        ("seed", -1),
        ("stream", "undeclared"),
        ("precision", "float16"),
        ("execution", {"workers": 1000, "threads": 1}),
    ],
)
def test_stochastic_precision_execution_contracts(field, value):
    g = modify(example("eeg"), "stages", 0, **{field: value})
    with pytest.raises(WorkflowError):
        builtins().validate(g)


@pytest.mark.parametrize(
    "family,expected",
    [
        ("eeg", {"reference", "psd", "bands"}),
        ("mri", {"segment", "qc", "surface"}),
        ("fmri", {"contrast", "roi"}),
        ("source", {"forward", "inverse", "reconstruct"}),
    ],
)
def test_selective_invalidation_and_key_agreement(family, expected, tmp_path):
    g = example(family)
    h = changed(g)
    e = Executor(builtins(), tmp_path / "cache")
    a = identities(g, e.registry, e.environment)
    b = identities(h, e.registry, e.environment)
    assert {s for s in a if a[s]["cache_key"] != b[s]["cache_key"]} == expected
    impact = invalidation(g, h)
    assert {s.id for s in g.stages if s.id in impact["invalidated"]} == expected
    assert impact["reasons"]
    same = replace(g, presentation={"palette": "purple", "layout": "vertical"})
    assert identities(same, e.registry, e.environment) == a
    assert invalidation(g, same)["invalidated"] == []


def test_environment_distinct_from_logical_and_result_bytes(tmp_path):
    e = Executor(builtins(), tmp_path / "cache")
    g = example("source")
    a = identities(g, e.registry, e.environment)
    env = copy.deepcopy(e.environment)
    env["machine"] = "other-architecture"
    b = identities(g, e.registry, env)
    assert all(a[n]["logical_key"] == b[n]["logical_key"] for n in a)
    assert all(a[n]["cache_key"] != b[n]["cache_key"] for n in a)
    env = copy.deepcopy(e.environment)
    env["libraries"]["numpy"] = "different"
    c = identities(g, e.registry, env)
    assert all(a[n]["logical_key"] != c[n]["logical_key"] for n in a)


@pytest.mark.parametrize("change", ["parameter", "seed", "geometry", "ontology", "unit"])
def test_omitted_semantics_cannot_collide(change, tmp_path):
    g = example("mri")
    e = Executor(builtins(), tmp_path / "cache")
    v = g.to_dict()
    if change == "parameter":
        v["stages"][3]["parameters"]["threshold"] = 1.01
    elif change == "seed":
        v["stages"][0]["seed"] = 18043
    elif change == "geometry":
        for a in v["artifacts"]:
            a["metadata"]["spatial_reference"]["space"] = "different-grid"
    elif change == "ontology":
        v["artifacts"][3]["metadata"]["ontology"]["1"] = "different-tissue"
    else:
        v["artifacts"][0]["metadata"]["units"] = {"intensity": "V"}
    if change in {"unit", "ontology"}:
        h = Graph.from_dict(v)
        assert invalidation(g, h)["invalidated"]
        with pytest.raises(WorkflowError):
            identities(h, e.registry, e.environment)
        return
    a = identities(g, e.registry, e.environment)
    b = identities(Graph.from_dict(v), e.registry, e.environment)
    assert any(a[n]["cache_key"] != b[n]["cache_key"] for n in a)


def test_coordinate_and_inference_guards():
    v = example("mri").to_dict()
    v["artifacts"][0]["metadata"]["spatial_reference"]["frame"] = "LPS"
    with pytest.raises(WorkflowError, match="RAS|Coordinate"):
        builtins().validate(Graph.from_dict(v))
    v = example("fmri").to_dict()
    v["artifacts"][0]["metadata"]["confirmatory_claim_allowed"] = True
    with pytest.raises(WorkflowError, match="descriptive"):
        builtins().validate(Graph.from_dict(v))


def test_lineage_includes_parameters_software_and_branching():
    g = example("mri")
    up = g.lineage("surface-surface")
    down = g.lineage("preprocess-processed", downstream=True)
    assert {"generate", "geometry", "preprocess", "segment", "surface"} <= set(up["nodes"])
    assert "qc" in down["nodes"] and "geometry" not in down["nodes"]
    assert all(len(edge) == 2 for edge in down["edges"])
    with pytest.raises(WorkflowError):
        g.lineage("missing")


def test_opaque_subjects_and_private_exports():
    a = opaque_subject("private-subject", secret=b"a" * 32)
    assert a == opaque_subject("private-subject", secret=b"a" * 32)
    assert a != opaque_subject("private-subject", secret=b"b" * 32)
    with pytest.raises(WorkflowError):
        opaque_subject("x", secret=b"short")
    exported = redact_export(
        {
            "subject_identity": a,
            "root": "/private/input",
            "metadata": {"note": "read /private/research/file", "secret": "hidden"},
            "restrictions": ["research only"],
            "reference": "dataset/input.json",
        }
    )
    assert exported["subject_identity"] == a and "root" not in exported
    assert "/private/" not in str(exported) and "hidden" not in str(exported)
    assert exported["reference"] == "dataset/input.json"
    assert exported["restrictions"] == ["research only"]
    assert "participant_name" not in redact_export({"participant_name": "private identifier"})
    restriction = redact_export("No redistribution; license at /private/research/license")
    assert restriction.startswith("No redistribution;") and "/private/" not in restriction
    assert redact_export("https://example.org/license") == "https://example.org/license"


def test_unknown_metadata_types_are_structured_errors():
    g = example("mri").to_dict()
    g["artifacts"][0]["metadata"] = None
    with pytest.raises(WorkflowError):
        Graph.from_dict(g).order()


def test_nonstring_mapping_keys_cannot_collapse_and_external_arrays_are_snapshots():
    from soma.workflow.runtime import normalized

    with pytest.raises(WorkflowError):
        normalized({1: "first", "1": "second"})
    a = np.arange(3.0)
    snapshot = normalized({"data": a})
    a[0] = 999
    assert snapshot["data"][0] == 0 and not snapshot["data"].flags.writeable
