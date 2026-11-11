"""Aggregate privacy, scientific interpretation and old/new protocol comparison guards."""

import copy

import pytest

from soma.eeg_benchmark.protocol import MODELS, VARIANTS
from soma.eeg_benchmark.report import aggregate_export, compare, validate_aggregate


@pytest.fixture
def aggregate():
    rows = []
    for mode in ["within-subject", "cross-subject"]:
        for model in MODELS:
            rows.append(
                {
                    "model": model,
                    "mode": mode,
                    "planned_subjects": 2,
                    "complete_subjects": 2,
                    "missing_subjects": 0,
                    "balanced_accuracy": {
                        "mean": 0.5,
                        "median": 0.5,
                        "lower": 0.5,
                        "upper": 0.5,
                        "n_subjects": 2,
                        "unit": "subject",
                    },
                    "metrics": {"brier": None, "log_loss": None},
                }
            )
    return {
        "schema": "soma.eeg.benchmark-aggregate/1.0.0",
        "protocol_fingerprint": "a" * 64,
        "status": "COMPLETE",
        "variants": [{"variant": v, "methods": copy.deepcopy(rows)} for v in VARIANTS],
        "wall_seconds": 0.0,
        "cpu_seconds": 0.0,
        "external_replication": False,
        "confirmatory_claim_allowed": False,
        "participant_rows_exported": False,
        "new_external_evidence": "NOT_AVAILABLE",
        "warnings": ["Fictional metadata fixture"],
    }


@pytest.mark.parametrize(
    "fault",
    [
        "subject",
        "private",
        "missing_model",
        "missing_variant",
        "confirmatory",
        "external",
        "p_value",
        "calibration",
        "adaptation",
    ],
)
def test_no_private_export_or_false_interpretation(aggregate, fault):
    if fault == "subject":
        aggregate["variants"][0]["methods"][0]["complete_subjects"] = 1
    elif fault == "private":
        aggregate["subject"] = "private-person"
    elif fault == "missing_model":
        aggregate["variants"][0]["methods"].pop()
    elif fault == "missing_variant":
        aggregate["variants"].pop()
    elif fault == "confirmatory":
        aggregate["confirmatory_claim_allowed"] = True
    elif fault == "external":
        aggregate["external_replication"] = True
    elif fault == "p_value":
        aggregate["variants"][0]["null_diagnostics"] = {
            "multiband_lr": {"p_value": 0.01, "exchangeability_attested": False}
        }
    elif fault == "calibration":
        next(r for r in aggregate["variants"][0]["methods"] if r["model"] == "riemann_mdm")[
            "metrics"
        ]["brier"] = 0.1
    else:
        aggregate["variants"][0]["adaptation"] = [
            {
                "target_supervised": False,
                "labeled_target_trials": 4,
                "test_data_used_for_fitting": False,
            }
        ]
    with pytest.raises(ValueError):
        validate_aggregate(aggregate)


def test_historical_accuracy_comparison_requires_same_protocol(aggregate):
    other = copy.deepcopy(aggregate)
    other["protocol_fingerprint"] = "b" * 64
    assert compare(aggregate, other)["status"] == "INCOMPATIBLE_PROTOCOLS"
    assert not compare(aggregate, aggregate)["cache_interchangeability"]


def test_private_rows_never_exported(tmp_path):
    with pytest.raises(ValueError, match="cannot be exported"):
        aggregate_export(tmp_path, None, b"", include_private=True)


@pytest.mark.parametrize("field", ["subject", "subject_key", "trial_id", "train_trial_ids"])
def test_nested_participant_export_rejected(aggregate, field):
    aggregate["variants"][0]["methods"][0][field] = "fictional-private-identifier"
    with pytest.raises(ValueError, match="Participant"):
        validate_aggregate(aggregate)
