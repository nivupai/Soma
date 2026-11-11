"""Focused safe archive commands; no external human-data acquisition."""

import json
from pathlib import Path

import typer

from soma.human.cli import emit
from soma.human.permissions import PermissionEvidence
from soma.model_archive.acquisition import acquisition_plan, verify_transfer
from soma.model_archive.archive import (
    frozen_prediction,
    inspect_archive,
    numerical_receipt,
    verify_release,
)
from soma.results.io import load_result, read_json

model_app = typer.Typer(help="Private source-only numeric model release; no pickle")


def access(
    permission: Path | None, notice: Path | None
) -> tuple[PermissionEvidence | None, bytes | None]:
    return (
        PermissionEvidence.from_dict(read_json(permission)) if permission else None,
        notice.read_bytes() if notice else None,
    )


@model_app.command("archive")
def archive(request: Path) -> None:
    from soma.model_archive.runtime import train_source

    emit(train_source(read_json(request)))


@model_app.command("inspect")
def inspection(path: Path, identity: str) -> None:
    d = inspect_archive(path, identity)
    emit(
        {
            k: d[k]
            for k in [
                "id",
                "dataset",
                "protocol_fingerprint",
                "cohort",
                "historical_m22",
                "weights_redistribution",
            ]
        }
    )


@model_app.command("verify")
def verification(
    path: Path,
    identity: str,
    probe: Path,
    permission: Path | None = None,
    notice: Path | None = None,
) -> None:
    p, n = access(permission, notice)
    emit(verify_release(path, identity, probe, permission=p, notice=n))


@model_app.command("predict")
def prediction(
    path: Path,
    identity: str,
    model: str,
    features: Path,
    output: Path,
    permission: Path | None = None,
    notice: Path | None = None,
) -> None:
    from soma.model_archive.archive import authorize

    d = inspect_archive(path, identity)
    p, n = access(permission, notice)
    authorize(d, p, n)
    e, a = load_result(features)
    contract = e["payload"]["values"]["contract"]
    labels, scores, probabilities = frozen_prediction(
        path,
        identity,
        model,
        contract,
        a["X"],
        a["powers"],
        a["covariances"],
        permission=p,
        notice=n,
    )
    numeric = {"labels": labels, "scores": scores}
    if probabilities is not None:
        numeric["probabilities"] = probabilities
    numerical_receipt(
        {"release_id": identity, "model": model, "external_validation": False},
        numeric,
        output,
        "soma.model-prediction",
    )
    emit({"status": "PREDICTED_PRIVATE", "trials": len(labels), "no_refit": True})


@model_app.command("compare")
def comparison(left: Path, left_id: str, right: Path, right_id: str) -> None:
    a, b = inspect_archive(left, left_id), inspect_archive(right, right_id)
    same = all(
        a[k] == b[k]
        for k in [
            "protocol_fingerprint",
            "source_fingerprint",
            "contract",
            "environment",
            "implementation",
        ]
    )
    emit(
        {
            "same_release": left_id == right_id,
            "same_declared_design_environment": same,
            "cache_interchangeability": False,
            "independent_validation": False,
        }
    )


def acquisition_command(output: Path) -> None:
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(acquisition_plan(), indent=2) + "\n")
    emit({"status": "EXTERNAL_DATA_ACQUISITION_BLOCKED", "downloaded": 0})


def transfer_command(path: Path, identity: str, candidate: str = "bnci2014-001") -> None:
    emit(verify_transfer(path, identity, candidate))
