"""Known-mixture synthetic benchmark; no human EEG, network or external registration."""

from pathlib import Path
from tempfile import TemporaryDirectory

from soma.decoding.synthetic import simulate_decoding
from soma.eeg_benchmark.evaluation import bank, evaluate, select
from soma.eeg_benchmark.protocol import MODELS, benchmark_protocol, configuration, design
from soma.eeg_benchmark.statistics import subject_table, summarize
from soma.workflow.model import digest


def run():
    value = design(3, 2)
    p = configuration(value, "primary")
    data, _ = simulate_decoding(seed=22042, n_subjects=5, n_trials=6, effect=0.8, noise=0.1)
    features = bank(data, p)
    selected, _, _ = select(features, p, [1, 2, 3], [4, 5])
    sealed = benchmark_protocol(value, digest({"synthetic": "known-mixture-v22"}))
    with TemporaryDirectory(prefix="soma-eeg-benchmark-") as directory:
        pred, cells, _ = evaluate(
            features, p, [1, 2, 3], [4, 5], selected, Path(directory), sealed.protocol.fingerprint
        )
    rows = subject_table(pred, [4, 5], p["evaluation_runs"])
    summary = summarize(rows, p)
    assert all(c["status"] == "COMPLETE" for c in cells)
    return {
        "synthetic_only": True,
        "actual_human_data_accessed": False,
        "protocol_fingerprint": sealed.protocol.fingerprint,
        "models": list(MODELS),
        "complete_cells": len(cells),
        "source_subjects": 3,
        "target_subjects": 2,
        "balanced_accuracy": [
            {"model": r["model"], "mode": r["mode"], "mean": r["balanced_accuracy"]["mean"]}
            for r in summary["methods"]
        ],
        "subject_bootstrap_unit": "subject",
        "confirmatory_claim_allowed": False,
    }


if __name__ == "__main__":
    print(run())
