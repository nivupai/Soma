"""Registered metadata only: no implicit execution, unsafe paths or array materialization."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.protocol.binding import example_protocol, example_snapshot
from soma.protocol.model import seal, write_seal
from soma.protocol.replay import run, write_execution


def test_empty_browser_does_not_execute_or_invent_history(tmp_path):
    with patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("GET executed")):
        with TestClient(
            create_app(Registry(Configuration()), tmp_path), base_url="http://127.0.0.1"
        ) as client:
            assert len(client.get("/api/protocols").json()) == 4
            assert client.get("/api/replays").json() == []
            receipt = client.get("/api/protocols/demo-protocol-fmri").json()
            assert not receipt["validation_receipt"]["external_preregistration_verified"]
            assert client.get("/api/protocols/unknown").status_code == 404


def test_saved_comparison_lineage_and_metadata_privacy(tmp_path):
    protocol = example_protocol("source")
    sealed = seal(protocol)
    snap = example_snapshot(protocol)
    a = run(sealed, snap, tmp_path / "cache", sequence=1)
    b = run(sealed, snap, tmp_path / "cache", sequence=2, reference=a)
    paths = [write_execution(r, tmp_path / n) for r, n in [(a, "left"), (b, "right")]]
    write_seal(sealed, tmp_path / "seal.json")
    entries = [
        Entry(
            id=n,
            kind="execution",
            label=n,
            root="r",
            file=str(p.relative_to(tmp_path)),
            synthetic=True,
        )
        for n, p in zip(["left", "right"], paths, strict=True)
    ]
    entries.append(
        Entry(
            id="sealed", kind="protocol", label="Sealed", root="r", file="seal.json", synthetic=True
        )
    )
    registry = Registry(Configuration(roots={"r": str(tmp_path)}, entries=entries))
    with patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("GET executed")):
        with TestClient(create_app(registry, tmp_path / "jobs"), base_url="http://127.0.0.1") as c:
            assert [r["sequence"] for r in c.get("/api/replays").json()] == [1, 2]
            response = c.get("/api/replay-comparison?left=left&right=right")
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["numerically_identical"] and result["authorized"]
            assert not result["cache_interchangeability"]
            assert len(result["numerical_comparisons"]) == 1
            assert str(tmp_path) not in response.text
            graph = c.get("/api/replays/left/lineage/0")
            assert graph.status_code == 200, graph.text
            assert len(graph.json()["nodes"]) == 8
            assert c.get("/api/replays/left/lineage/99").status_code == 422
            assert (
                c.get("/api/protocol-comparison?left=sealed&right=sealed").json()["status"]
                == "IDENTICAL"
            )
            assert c.get("/api/replays/%2e%2e%2fsecret").status_code == 404
    # A configured file is resolved again on every access, including symlink replacement.
    Path(paths[0]).unlink()
    Path(paths[0]).symlink_to(tmp_path.parent / "not-allowed")
    with TestClient(create_app(registry, tmp_path / "jobs2"), base_url="http://127.0.0.1") as c:
        assert c.get("/api/replays/left").status_code == 404
