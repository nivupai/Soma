"""Focused external audit, planning, execution and inspection commands."""

from pathlib import Path

import typer

from soma.external_eeg import validation_cli
from soma.external_eeg.contracts import candidate_audit, plan, seal_plan
from soma.external_eeg.data import inventory
from soma.external_eeg.models import import_model
from soma.external_eeg.runtime import compare, read_receipt, run, write_receipt
from soma.human.cli import emit
from soma.human.evidence import read_bundle
from soma.human.permissions import PermissionEvidence
from soma.model_archive.cli import acquisition_command, transfer_command
from soma.protocol.model import read_seal, write_seal
from soma.results.io import read_json

external_app = typer.Typer(help="External EEG: no download or implicit frozen-model replacement")


@external_app.command("plan")
def planning(
    root: Path, output: Path, mode: str = "EXTERNAL_REFIT", split: str = "subject"
) -> None:
    from soma.datasets.human_mri import safe_local_output

    safe_local_output(output)
    output.mkdir(parents=True, exist_ok=False)
    inv = inventory(root)
    sealed = seal_plan(plan(mode, split), inv["fingerprint"], {})
    write_seal(sealed, output / "protocol.json")
    import json

    (output / "inventory.local.json").write_text(json.dumps(inv, indent=2))
    write_receipt(candidate_audit(), output / "audit")
    emit(
        {
            "status": "SEALED_BEFORE_OUTCOMES",
            "protocol_fingerprint": sealed.protocol.fingerprint,
            "available_files": inv["available"],
            "planned_files": 18,
            "human_execution": "BLOCKED"
            if inv["available"] != 18
            else "REQUIRES_CURRENT_PERMISSION",
        }
    )


@external_app.command("verify-model")
def model(path: Path, expected_id: str) -> None:
    d, _ = import_model(path, expected_id)
    emit(
        {
            "status": "VALID_NUMERIC_CAPSULE",
            "id": d["id"],
            "model": d["model"],
            "original_m22": False,
            "fidelity": "Numeric identity is not authenticated historical origin",
        }
    )


@external_app.command("run")
def execution(
    root: Path,
    plan_dir: Path,
    output: Path,
    permission: Path | None = None,
    notice: Path | None = None,
    bundle: Path | None = None,
    references: Path | None = None,
) -> None:
    d = run(
        read_seal(plan_dir / "protocol.json"),
        root,
        output,
        PermissionEvidence.from_dict(read_json(permission)) if permission else None,
        notice.read_bytes() if notice else None,
        expected_inventory=read_json(plan_dir / "inventory.local.json"),
        bundle=read_bundle(bundle) if bundle else None,
        references={k: (Path(v["root"]), v["relative"]) for k, v in read_json(references).items()}
        if references
        else None,
    )
    emit(
        {
            "status": d["status"],
            "performance": d.get("performance", []),
            "blockers": d.get("blockers", []),
        }
    )


@external_app.command("compare")
def comparison(left: Path, right: Path) -> None:
    emit(compare(read_receipt(left), read_receipt(right)))


@external_app.command("domain-shift")
def domain_shift(receipt: Path) -> None:
    emit(read_receipt(receipt)["domain_shift"])


@external_app.command("verify")
def verification(receipt: Path) -> None:
    d = read_receipt(receipt)
    emit(
        {
            "status": "VERIFIED",
            "scientific_state": d["status"],
            "meaning": "native integrity and privacy checks; not external replication",
        }
    )


external_app.command("acquisition-plan")(acquisition_command)
external_app.command("verify-transfer")(transfer_command)


external_app.command("acquisition-manifest")(validation_cli.acquisition_manifest)
external_app.command("acquire")(validation_cli.acquisition_run)
external_app.command("snapshot")(validation_cli.snapshot_check)
external_app.command("validation-plan")(validation_cli.validation_plan)
external_app.command("validation-run")(validation_cli.validation_run)
external_app.command("validation-verify")(validation_cli.validation_verify)
external_app.command("validation-shift")(validation_cli.domain_shift)
external_app.command("source-runtime-check")(validation_cli.runtime_check)
