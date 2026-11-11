"""Strict aggregate-only export and verification; private participant rows stay local."""

import copy
from pathlib import Path
from typing import Any

from soma.core.provenance import sha256
from soma.eeg_benchmark.evaluation import native, read_native
from soma.eeg_benchmark.protocol import MODELS, VARIANTS
from soma.human.permissions import PermissionEvidence, check_permission
from soma.protocol.model import closed
from soma.workflow.model import digest
from soma.workflow.privacy import redact_export


def verify_execution(root: Path) -> dict[str, Any]:
    value = read_native(root / "execution/result.json")
    if (
        value["schema"] != "soma.eeg.benchmark-execution/1.0.0"
        or value["confirmatory_claim_allowed"] is not False
        or value["external_replication"] is not False
    ):
        raise ValueError("Invalid scientific interpretation")
    if [v["variant"] for v in value["variants"]] != list(VARIANTS):
        raise ValueError("Missing or reordered planned sensitivities")
    for summary in value["variants"]:
        folder = root / summary["variant"]
        if (
            summary["identity"] != value["identity"]
            or read_native(folder / "summary/result.json") != summary
        ):
            raise ValueError("Inconsistent benchmark receipt")
        expected = {
            (mode, model) for mode in ("within-subject", "cross-subject") for model in MODELS
        }
        if {(r["mode"], r["model"]) for r in summary["methods"]} != expected:
            raise ValueError("Missing model or outer evaluation")
        for row in summary["methods"]:
            if row["complete_subjects"] + row["missing_subjects"] != row["planned_subjects"]:
                raise ValueError("Missing subject results silently dropped")
            if row["planned_subjects"] != summary["planned_target_subjects"]:
                raise ValueError("Changed target cohort")
            ci = row["balanced_accuracy"]
            if ci and (
                not 0 <= ci["lower"] <= ci["upper"] <= 1
                or ci["unit"] != "subject"
                or ci["n_subjects"] != row["complete_subjects"]
            ):
                raise ValueError("Invalid subject uncertainty")
        for relative, expected_hash in summary["files"].items():
            path = (folder / relative).resolve(strict=True)
            if not path.is_relative_to(folder.resolve()) or sha256(path) != expected_hash:
                raise ValueError("Corrupted private benchmark artifact")
            if path.name == "result.json":
                read_native(path)
    return {
        "status": "VERIFIED",
        "identity": value["identity"],
        "variants": len(value["variants"]),
        "confirmation_authorized": False,
        "meaning": "integrity/consistency, not independent biological validation",
    }


def aggregate_export(
    root: Path, permission: PermissionEvidence, source: bytes, *, include_private: bool = False
) -> dict[str, Any]:
    if include_private:
        raise ValueError("Participant rows and raw signals cannot be exported")
    allowed = check_permission(
        permission,
        dataset="eegmmidb",
        version="1.0.0",
        purpose="methods_research",
        action="export_aggregate",
        source_content=source,
    )
    if not allowed["allowed"]:
        raise ValueError("Aggregate export is not supported by current use evidence")
    verify_execution(root)
    record = read_native(root / "execution/result.json")
    variants = []
    fields = {
        "variant",
        "methods",
        "comparisons",
        "subject_inclusion_influence",
        "adaptation",
        "null_diagnostics",
        "source_subjects",
        "planned_source_subjects",
        "target_subjects",
        "planned_target_subjects",
        "recordings_planned",
        "recordings_eligible",
        "trials_retained",
        "trials_proposed",
        "trials_rejected_or_unavailable",
        "failed_model_cells",
        "wall_seconds",
        "process_peak_rss_mib",
        "leakage_checks",
        "selected_parameters",
    }
    for row in record["variants"]:
        variants.append({k: copy.deepcopy(v) for k, v in row.items() if k in fields})
    result = {
        "schema": "soma.eeg.benchmark-aggregate/1.0.0",
        "protocol_fingerprint": record["protocol_fingerprint"],
        "status": record["status"],
        "variants": variants,
        "wall_seconds": record["wall_seconds"],
        "cpu_seconds": record["cpu_seconds"],
        "external_replication": False,
        "confirmatory_claim_allowed": False,
        "participant_rows_exported": False,
        "new_external_evidence": "NOT_AVAILABLE",
        "warnings": [
            "historically reused EEGBCI subjects; not untouched or external validation",
            "subject bootstrap conditional on fitted source models; fixed nonrandom cohort",
            "real temporal label exchangeability unverified; no nominal permutation p-values",
            "target-labeled adaptation is separate from zero-shot transfer",
            "no clinical, anatomical or other-modality authorization",
        ],
    }
    if redact_export(result) != result:
        raise ValueError("Private locations in aggregate output")
    return result


def save_aggregate(value: dict[str, Any], output: Path) -> None:
    validate_aggregate(value)
    native(value, output, computation="aggregate-eeg-benchmark")


def reject_participant_fields(value: Any) -> None:
    """Aggregate readers also refuse nested participant/cell payloads."""
    if isinstance(value, dict):
        forbidden = {
            "subject",
            "subject_key",
            "participant",
            "participant_id",
            "participant_key",
            "trial_id",
            "train_trial_ids",
            "test_trial_ids",
            "predictions",
            "rows",
            "files",
            "root",
            "path",
            "raw_subject",
        }
        if set(value) & forbidden:
            raise ValueError("Participant fields do not belong in an aggregate receipt")
        for item in value.values():
            reject_participant_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_participant_fields(item)


def validate_aggregate(value: dict[str, Any]) -> None:
    reject_participant_fields(value)
    if (
        value.get("schema") != "soma.eeg.benchmark-aggregate/1.0.0"
        or value.get("participant_rows_exported") is not False
        or value.get("confirmatory_claim_allowed") is not False
        or value.get("external_replication") is not False
    ):
        raise ValueError("Not a restricted aggregate benchmark")
    closed(
        value,
        {
            "schema",
            "protocol_fingerprint",
            "status",
            "variants",
            "wall_seconds",
            "cpu_seconds",
            "external_replication",
            "confirmatory_claim_allowed",
            "participant_rows_exported",
            "new_external_evidence",
            "warnings",
        },
    )
    if [r["variant"] for r in value["variants"]] != list(VARIANTS):
        raise ValueError("Missing sensitivities")
    for variant in value["variants"]:
        if {(r["mode"], r["model"]) for r in variant["methods"]} != {
            (mode, model) for mode in ("within-subject", "cross-subject") for model in MODELS
        }:
            raise ValueError("Incomplete method comparison")
    for variant in value["variants"]:
        for diagnostic in variant.get("null_diagnostics", {}).values():
            if (
                diagnostic.get("p_value") is not None
                or diagnostic.get("exchangeability_attested") is not False
            ):
                raise ValueError("Unverified exchangeability cannot yield a human p-value")
        for row in variant["methods"]:
            if row["complete_subjects"] + row["missing_subjects"] != row["planned_subjects"]:
                raise ValueError("Subject coverage cannot be changed after outcomes")
            if row["model"] == "riemann_mdm" and any(
                row["metrics"].get(k) is not None for k in ["brier", "log_loss"]
            ):
                raise ValueError("MDM margins are not calibrated probabilities")
        for adaptation in variant.get("adaptation", []):
            if (
                adaptation["target_supervised"] != (adaptation["labeled_target_trials"] > 0)
                or adaptation["test_data_used_for_fitting"] is not False
            ):
                raise ValueError("Adaptation cannot be labeled zero-shot or use test data")
    if redact_export(value) != value:
        raise ValueError("Private aggregate fields")


def read_aggregate(path: Path) -> dict[str, Any]:
    value = read_native(path)
    validate_aggregate(value)
    return value


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    validate_aggregate(left)
    validate_aggregate(right)
    if left["protocol_fingerprint"] != right["protocol_fingerprint"]:
        return {
            "status": "INCOMPATIBLE_PROTOCOLS",
            "numeric_comparison_authorized": False,
            "reason": (
                "cohort, preprocessing or estimand may differ"
                "; historical accuracy is not interchangeable"
            ),
        }
    return {
        "status": "SAME_DECLARED_PROTOCOL",
        "identical": digest(left) == digest(right),
        "external_replication": False,
        "cache_interchangeability": False,
        "confirmatory_claim_allowed": False,
    }
