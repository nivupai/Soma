"""Scientific round trips, dependency fingerprints and fault-injected recovery."""

import json

import numpy as np
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.pipeline.cache import decode
from soma.sdk.results import load_result
from soma.sdk.workflow import Executor, Graph, WorkflowError, builtins, changed, content, example
from soma.workflow.runtime import identities, permitted


@pytest.mark.parametrize("family", ["eeg", "mri", "fmri", "source"])
def test_real_cold_warm_and_selective_reuse(family, tmp_path):
    g = example(family)
    e = Executor(builtins(), tmp_path / "cache")
    cold = e.run(g)
    warm = e.resume(g)
    altered = e.run(changed(g))
    assert cold["status"] == warm["status"] == altered["status"] == "COMPLETE"
    assert all(not s["cached"] for s in cold["stages"])
    assert all(s["cached"] for s in warm["stages"])
    assert cold["outputs"] == warm["outputs"]
    assert any(s["cached"] for s in altered["stages"])
    assert any(not s["cached"] for s in altered["stages"])
    assert all(s["status"] == "VERIFIED_HIT" for s in e.plan(g)["stages"])
    if family == "fmri":
        statuses = {s["stage"]: s["cached"] for s in altered["stages"]}
        assert statuses["fit"] and not statuses["contrast"] and not statuses["roi"]


@pytest.mark.parametrize(
    "point",
    [
        "before_stage",
        "computation",
        "serialization",
        "before_publication",
        "after_publication",
        "before_status_update",
    ],
)
def test_interruption_resume_matches_uninterrupted(point, tmp_path):
    g = example("source")
    e = Executor(builtins(), tmp_path / "interrupted")

    def fault(stage, when):
        if stage == "forward" and when == point:
            raise InterruptedError("injected")

    interrupted = e.run(g, fault=fault, record=tmp_path / "journal.json")
    assert interrupted["status"] == "CANCELLED"
    assert interrupted["stages"][-1]["stage"] == "forward"
    resumed = e.resume(g)
    fresh = Executor(builtins(), tmp_path / "fresh").run(g)
    assert resumed["status"] == fresh["status"] == "COMPLETE"
    assert resumed["outputs"] == fresh["outputs"]
    cached = {s["stage"]: s["cached"] for s in resumed["stages"]}
    assert cached["geometry"]
    assert cached["forward"] == (point in {"after_publication", "before_status_update"})
    assert not list((tmp_path / "interrupted").glob(".building-*"))


def test_partial_serialization_disk_full_is_not_visible(monkeypatch, tmp_path):
    import soma.workflow.runtime as runtime

    original = runtime.save_result

    def partial(value, arrays, folder):
        folder.mkdir()
        (folder / "partial.npy").write_bytes(b"partial")
        raise OSError("injected ENOSPC")

    monkeypatch.setattr(runtime, "save_result", partial)
    g = example("source")
    e = Executor(builtins(), tmp_path / "cache")
    failed = e.run(g)
    assert failed["status"] == "FAILED" and failed["stages"][0]["reason"] == "OSError"
    assert not [p for p in (tmp_path / "cache").iterdir() if not p.name.startswith(".")]
    monkeypatch.setattr(runtime, "save_result", original)
    assert e.resume(g)["status"] == "COMPLETE"


def test_atomic_directory_publication_and_conflicting_content(tmp_path):
    g = example("source")
    e = Executor(builtins(), tmp_path / "cache")
    stage = g.order()[0]
    identity = identities(g, e.registry, e.environment)[stage.id]
    artifacts = {a.id: a for a in g.artifacts}
    seen = []

    def fault(name, point):
        if name == stage.id and point == "before_publication":
            seen.append(e.cache.lookup(stage, identity, artifacts, e.environment, {}))

    assert e.run(g, fault=fault)["status"] == "COMPLETE"
    assert seen == [None]
    with pytest.raises(WorkflowError, match="Conflicting"):
        e.cache.publish(
            stage,
            identity,
            artifacts,
            {"geometry": {"different": 1}},
            e.environment,
            lambda *args: None,
            {},
        )


@pytest.mark.parametrize(
    "damage",
    [
        "array",
        "missing-array",
        "metadata",
        "missing-metadata",
        "receipt",
        "input-fingerprint",
        "producer-version",
        "schema-version",
    ],
)
def test_corrupted_published_entries_fail_without_repair(damage, tmp_path):
    g = example("source")
    e = Executor(builtins(), tmp_path / "cache")
    assert e.run(g)["status"] == "COMPLETE"
    identity = identities(g, e.registry, e.environment)["forward"]
    directory = tmp_path / "cache" / identity["cache_key"]
    metadata = directory / "forward/result.json"
    array = next((directory / "forward/arrays").glob("*.npy"))
    if damage == "array":
        array.write_bytes(b"corrupt")
    elif damage == "missing-array":
        array.unlink()
    elif damage == "metadata":
        metadata.write_bytes(b"{")
    elif damage == "missing-metadata":
        metadata.unlink()
    elif damage in {"receipt", "input-fingerprint"}:
        p = directory / "receipt.json"
        v = json.loads(p.read_text())
        if damage == "receipt":
            v["schema"] = "future"
        else:
            v["input_contents"]["geometry"] = "0" * 64
        p.write_text(json.dumps(v))
    else:
        from soma.results.contracts import seal

        v = json.loads(metadata.read_text())
        v["producer_version" if damage == "producer-version" else "schema_version"] = "99.0.0"
        metadata.write_text(json.dumps(seal(v)))
    before = {
        str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }
    failed = e.resume(g)
    assert failed["status"] == "FAILED" and failed["stages"][-1]["stage"] == "forward"
    assert "verification" in failed["stages"][-1]["reason"]
    assert before == {
        str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }
    with pytest.raises(WorkflowError):
        e.plan(g)


def test_cancellation_and_dry_run_never_execute(tmp_path):
    g = example("source")
    e = Executor(builtins(), tmp_path / "cache")
    assert e.plan(g)["execution_started"] is False
    assert not (tmp_path / "cache").exists()
    r = e.run(g, cancelled=lambda: True)
    assert r["status"] == "CANCELLED" and not (tmp_path / "cache").exists()


def test_missing_or_changed_external_input_prevents_every_stage(tmp_path):
    base = example("source")
    v = base.to_dict()
    v["stages"] = v["stages"][1:]
    v["artifacts"][0].update(producer=None, fingerprint=content({"data": np.arange(3)}))
    g = Graph.from_dict(v)
    e = Executor(builtins(), tmp_path / "cache")
    with pytest.raises(WorkflowError, match="unavailable"):
        e.run(g)
    with pytest.raises(WorkflowError, match="fingerprint"):
        e.run(g, inputs={"geometry-geometry": {"data": np.arange(4)}})
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize(
    "reference", ["../escape", "/private/input", "a/../../x", "a\\x", "file://x"]
)
def test_traversal_rejected(reference, tmp_path):
    with pytest.raises(WorkflowError):
        permitted(tmp_path, reference)


def test_symlink_escape_and_symlinked_cache_root(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "x").write_text("private")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(other, target_is_directory=True)
    with pytest.raises(WorkflowError):
        permitted(root, "link/x")
    (root / "cache").symlink_to(other, target_is_directory=True)
    r = Executor(builtins(), root / "cache").run(example("source"))
    assert r["status"] == "FAILED"
    assert (other / "x").read_text() == "private"


def test_cli_commands_operate_on_actual_graph_and_saved_run(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(example("source").to_dict()))
    runner = CliRunner()
    cache = tmp_path / "cache"
    record = tmp_path / "run.json"
    for command in ["inspect", "validate", "plan", "explain-cache"]:
        response = runner.invoke(
            app,
            [
                "workflow",
                command,
                str(path),
                *(["--cache-root", str(cache)] if command in {"plan", "explain-cache"} else []),
            ],
        )
        assert response.exit_code == 0, response.output
    response = runner.invoke(
        app, ["workflow", "run", str(path), "--cache-root", str(cache), "--dry-run"]
    )
    assert response.exit_code == 0 and not cache.exists()
    response = runner.invoke(
        app, ["workflow", "run", str(path), "--cache-root", str(cache), "--record", str(record)]
    )
    assert response.exit_code == 0, response.output
    for command in ["resume", "verify"]:
        response = runner.invoke(
            app, ["workflow", command, str(record), "--cache-root", str(cache)]
        )
        assert response.exit_code == 0, response.output
    response = runner.invoke(app, ["workflow", "lineage", str(record), "reconstruct-source"])
    assert response.exit_code == 0 and "forward" in response.output


def test_OLS_contrast_statistics_match_existing_Soma_contrast(tmp_path):
    from soma.sdk.fmri import Contrast, contrast, fit
    from soma.workflow.operations import functional, model_config

    g = example("fmri")
    e = Executor(builtins(), tmp_path / "cache")
    assert e.run(g)["status"] == "COMPLETE"
    ids = identities(g, e.registry, e.environment)

    def get(stage, port):
        result, arrays = load_result(
            tmp_path / "cache" / ids[stage]["cache_key"] / port / "result.json"
        )
        return decode(result["payload"]["values"], arrays, {})

    bold = get("generate", "bold")
    model = fit(functional(bold), model_config())
    expected = contrast(model, Contrast("task", {"task": 1.0}))
    stored = get("contrast", "contrast")
    mask = functional(bold).mask.array().astype(bool)
    np.testing.assert_allclose(
        stored["effect"],
        np.asarray(expected.maps["effect_size"].dataobj)[mask],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        stored["variance"],
        np.asarray(expected.maps["effect_variance"].dataobj)[mask],
        rtol=1e-12,
        atol=1e-12,
    )
    assert stored["confirmatory_claim_allowed"] is False


def test_shared_input_and_identical_parallel_operations_do_not_conflict(tmp_path):
    from dataclasses import replace

    g = example("source")
    inverse = next(s for s in g.stages if s.id == "inverse")
    artifact = next(a for a in g.artifacts if a.id == "inverse-inverse")
    branch = replace(inverse, id="parallel-inverse", outputs={"inverse": "parallel-kernel"})
    h = replace(
        g,
        stages=(*g.stages, branch),
        artifacts=(
            *g.artifacts,
            replace(artifact, id="parallel-kernel", producer="parallel-inverse"),
        ),
    )
    e = Executor(builtins(), tmp_path / "cache")
    result = e.run(h)
    assert result["status"] == "COMPLETE"
    assert result["outputs"]["parallel-kernel"] == result["outputs"]["inverse-inverse"]
    assert all(s["cached"] for s in e.resume(h)["stages"])


def test_live_memory_policy_rejects_nonfinite_or_excessive_values_before_science(tmp_path):
    from soma.workflow.runtime import numeric_bytes

    with pytest.raises(WorkflowError):
        numeric_bytes({"bad": np.array([np.nan])})
    with pytest.raises(WorkflowError):
        numeric_bytes({"bad": np.zeros(64 * 1024**2 // 8 + 1)})


def test_cooperating_concurrent_publishers_cannot_replace_committed_artifacts(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    g = example("source")
    a = Executor(builtins(), tmp_path / "shared")
    b = Executor(builtins(), tmp_path / "shared")
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda executor: executor.run(g), [a, b]))
    assert all(r["status"] == "COMPLETE" for r in runs)
    assert runs[0]["outputs"] == runs[1]["outputs"]
    assert all(r["cached"] for r in a.resume(g)["stages"])
