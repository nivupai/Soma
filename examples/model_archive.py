"""Complete fictional fitted release and prediction-only reload, never human accuracy."""

from pathlib import Path
from tempfile import TemporaryDirectory

from soma.external_eeg.synthetic import fictional
from soma.model_archive.archive import verify_release
from soma.model_archive.protocol import seal_training
from soma.model_archive.training import archive_models


def run():
    with TemporaryDirectory(prefix="soma-model-archive-") as directory:
        root = Path(directory) / "release"
        release = archive_models(fictional(), seal_training("a" * 64, True), root)
        checked = verify_release(
            root / "manifest/result.json", release["id"], root / "probe/result.json"
        )
        return {
            "synthetic_only": True,
            "five_complete_models": len(release["models"]) == 5,
            "labels_exact": all(r["labels_exact"] for r in checked["models"].values()),
            "scores_within_frozen_tolerance": all(
                r["score_max_abs_error"] < 1e-9 for r in checked["models"].values()
            ),
            "manifest_verified": True,
            "human_external_evaluation": "BLOCKED",
            "private_weights_exported": False,
            "original_m22": False,
        }
