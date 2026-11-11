"""Known-mixture external sessions and safe model import; no human data."""

from pathlib import Path
from tempfile import TemporaryDirectory

from soma.external_eeg.contracts import compatibility, feature_contract, plan
from soma.external_eeg.study import evaluate
from soma.external_eeg.synthetic import fictional


def run():
    data = fictional()
    outcomes = {}
    with TemporaryDirectory(prefix="soma-external-eeg-") as folder:
        for split in ["subject", "session"]:
            report, _ = evaluate(data, plan(split=split), Path(folder) / split, synthetic=True)
            assert report["status"] == "COMPLETE" and not report["original_m22_model"]
            outcomes[split] = [
                {
                    "model": r["model"],
                    "mean": r["balanced_accuracy"]["mean"],
                    "subjects": r["complete_subjects"],
                }
                for r in report["performance"]
            ]
    return {
        "synthetic_only": True,
        "human_evaluation": "BLOCKED",
        "actual_human_data_accessed": False,
        "original_m22_recovered": False,
        "expected_model_count": 5,
        "outcomes": outcomes,
        "reference_mismatch": compatibility(
            feature_contract("eegbci-average-all-eeg"), feature_contract()
        )["status"],
        "target_labels_used_for_fitting": False,
        "subject_unit": "participant",
        "p_value": None,
    }
