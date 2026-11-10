"""Graph navigation is metadata-only, bounded, allowlisted and path-redacted."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.explorer_api.app import create_app
from services.explorer_api.registry import Configuration, Entry, Registry
from soma.sdk.workflow import example


def test_demo_graph_navigation_never_executes_or_loads_arrays():
    with (
        patch("soma.workflow.runtime.Executor.run", side_effect=AssertionError("execution")),
        patch("soma.results.io.load_result", side_effect=AssertionError("arrays")),
    ):
        with TestClient(create_app(), base_url="http://127.0.0.1") as client:
            index = client.get("/api/workflows").json()
            assert len(index) == 4
            for row in index:
                response = client.get("/api/workflows/" + row["id"])
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "NOT_RUN" and data["edges"]
                assert {"artifact", "stage"} == {n["node_type"] for n in data["nodes"]}
                assert all(n["data"]["cache"] == "NOT_ASSESSED" for n in data["nodes"])
                leaf = data["nodes"][-1]["id"]
                ancestry = client.get("/api/workflows/" + row["id"] + "/lineage/" + leaf).json()
                assert ancestry["node"] == leaf
            assert client.post("/api/workflows/demo-workflow-eeg/run").status_code in {404, 405}
            assert client.get("/api/workflows/unknown").status_code == 404


def test_configured_saved_graph_and_journal_redact_private_paths(tmp_path):
    g = example("source").to_dict()
    g["artifacts"][0]["metadata"]["private_note"] = "at /private/participant/file"
    path = tmp_path / "record.json"
    path.write_text(
        json.dumps(
            {
                "schema": "soma.workflow.run/1",
                "graph": g,
                "status": "FAILED",
                "environment": {"root": "/private/work", "python": "recorded"},
                "stages": [
                    {
                        "stage": "forward",
                        "status": "FAILED",
                        "reason": "private /private/location",
                        "cached": False,
                        "wall_s": 0.1,
                        "validation": "NOT_RUN",
                    }
                ],
            }
        )
    )
    registry = Registry(
        Configuration(
            roots={"records": str(tmp_path)},
            entries=[
                Entry(
                    id="workflow-record",
                    kind="workflow",
                    label="Selected run",
                    root="records",
                    file=path.name,
                )
            ],
        )
    )
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as client:
        response = client.get("/api/workflows/workflow-record")
        assert response.status_code == 200
        assert "/private/" not in response.text
        assert response.json()["status"] == "FAILED"
        assert (
            next(n for n in response.json()["nodes"] if n["id"] == "forward")["data"]["runtime_s"]
            == 0.1
        )
        path.write_text("{")
        assert client.get("/api/workflows/workflow-record").status_code == 422


def test_graph_symlink_escape_rechecked_on_every_request(tmp_path):
    (tmp_path / "g.json").write_text(json.dumps(example("eeg").to_dict()))
    registry = Registry(
        Configuration(
            roots={"records": str(tmp_path)},
            entries=[
                Entry(
                    id="configured-dag", kind="workflow", label="DAG", root="records", file="g.json"
                )
            ],
        )
    )
    with TestClient(create_app(registry), base_url="http://127.0.0.1") as client:
        (tmp_path / "g.json").unlink()
        (tmp_path / "g.json").symlink_to("/dev/null")
        assert client.get("/api/workflows/configured-dag").status_code == 422


def test_malformed_record_cannot_claim_complete_or_trigger_server_errors():
    import pytest

    from soma.workflow.model import WorkflowError
    from soma.workflow.view import graph_view

    for rows in [None, [{"stage": "missing"}], []]:
        with pytest.raises(WorkflowError):
            graph_view(
                example("source"),
                {
                    "schema": "soma.workflow.run/1",
                    "status": "COMPLETE",
                    "environment": {},
                    "stages": rows,
                },
            )
