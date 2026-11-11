"""Typed focused EEG benchmark APIs, backed by existing Soma scientific contracts."""

from pathlib import Path
from typing import Any

from soma.eeg_benchmark.data import inventory as inventory
from soma.eeg_benchmark.protocol import benchmark_protocol as benchmark_protocol
from soma.eeg_benchmark.protocol import design as design
from soma.eeg_benchmark.protocol import inspect_protocol as inspect_protocol
from soma.eeg_benchmark.protocol import validate_design as validate_design
from soma.eeg_benchmark.report import aggregate_export as aggregate_export
from soma.eeg_benchmark.report import compare as compare
from soma.eeg_benchmark.report import read_aggregate as read_aggregate
from soma.eeg_benchmark.report import save_aggregate as save_aggregate
from soma.eeg_benchmark.report import verify_execution as verify_execution
from soma.eeg_benchmark.runner import run_benchmark as run_benchmark
from soma.external_eeg.contracts import candidate_audit as external_audit
from soma.external_eeg.contracts import compatibility as external_compatibility
from soma.external_eeg.contracts import plan as external_plan
from soma.external_eeg.contracts import seal_plan as seal_external_plan
from soma.external_eeg.data import inventory as external_inventory
from soma.external_eeg.models import import_model as import_external_model
from soma.external_eeg.models import predict as predict_frozen_external
from soma.external_eeg.runtime import compare as compare_external
from soma.external_eeg.runtime import read_receipt as verify_external
from soma.external_eeg.runtime import run as run_external
from soma.model_archive.acquisition import acquisition_plan as model_acquisition_plan
from soma.model_archive.acquisition import verify_transfer as model_transfer_compatibility
from soma.model_archive.archive import aggregate_summary as model_release_summary
from soma.model_archive.archive import frozen_prediction as predict_archived_model
from soma.model_archive.archive import inspect_archive as inspect_model_archive
from soma.model_archive.archive import verify_release as verify_model_release
from soma.model_archive.protocol import seal_training as seal_model_training
from soma.model_archive.protocol import training_protocol as model_training_protocol
from soma.model_archive.training import archive_models as archive_fitted_models

__all__ = [
    "inventory",
    "benchmark_protocol",
    "design",
    "inspect_protocol",
    "validate_design",
    "aggregate_export",
    "compare",
    "read_aggregate",
    "save_aggregate",
    "verify_execution",
    "run_benchmark",
    "external_audit",
    "external_compatibility",
    "external_plan",
    "seal_external_plan",
    "external_inventory",
    "import_external_model",
    "predict_frozen_external",
    "compare_external",
    "verify_external",
    "run_external",
    "external_domain_shift",
]


def external_domain_shift(receipt: Path) -> dict[str, Any]:
    """Inspect validated aggregate shift evidence without fitting or loading signals."""
    return dict(verify_external(receipt)["domain_shift"])


__all__ += [
    "model_acquisition_plan",
    "model_transfer_compatibility",
    "predict_archived_model",
    "inspect_model_archive",
    "verify_model_release",
    "seal_model_training",
    "model_training_protocol",
    "archive_fitted_models",
    "model_release_summary",
]
