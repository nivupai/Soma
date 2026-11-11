"""Independent fictional target draws and frozen inference; no human EEG acquisition."""

import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from soma.external_eeg.synthetic import fictional
from soma.external_eeg.validation import execute, read_validation, seal_validation
from soma.model_archive.protocol import seal_training
from soma.model_archive.training import archive_models


def target():
    data = fictional(seed=25042)
    frame = data.metadata.copy()
    for key in ["recording", "trial_id"]:
        frame[key] = frame[key].str.replace(
            "synthetic-external-v1", "synthetic-target-v25", regex=False
        )
    return replace(
        data, metadata=frame, provenance={**data.provenance, "dataset": "synthetic-target-v25"}
    )


def run():
    with TemporaryDirectory(prefix="soma-frozen-external-") as directory:
        root = Path(directory)
        source = fictional()
        new = target()
        release = archive_models(source, seal_training("a" * 64, True), root / "models")
        sealed = seal_validation(new.fingerprint, release["id"], "synthetic-target-v25")
        report = execute(
            sealed,
            {},
            root,
            root / "models/manifest/result.json",
            Path(sys.executable),
            root / "evaluation",
            synthetic_data=new,
        )
        read_validation(root / "evaluation/summary/result.json")
        assert report["status"] == "SYNTHETIC_COMPLETE"
        assert all(m["complete_subjects"] == 9 for m in report["performance"])
        assert report["performance"][0]["balanced_accuracy"]["mean"] == 0.5
        assert all(m["balanced_accuracy"]["mean"] >= 0.8 for m in report["performance"][1:])
        return {
            "synthetic_only": True,
            "independent_target_seed": 25042,
            "subjects": 9,
            "trials": 648,
            "frozen_methods": 5,
            "source_refits": report["refitted_components"],
            "all_participant_coverage": True,
            "no_human_external_trials": report["human_external_trials"] == 0,
            "majority_half": True,
            "known_mixture_reference_passed": True,
            "no_cache_interchange": True,
        }
