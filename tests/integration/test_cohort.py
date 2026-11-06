import os
from pathlib import Path

import pandas as pd
import pytest

from soma.datasets.eegbci import recording_path
from soma.experiments.cohort import run_cohort
from soma.experiments.config import CohortConfig

pytestmark = pytest.mark.integration


def test_cached_subject1_multirun_cohort(tmp_path):
    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not all(recording_path(root, 1, run).is_file() for run in (4, 8, 12)):
        pytest.skip("Explicitly fetch S001R04/R08/R12; tests never download")
    result = run_cohort(
        root, tmp_path / "cohort", CohortConfig(subjects=(1,), plots=False), tmp_path / "cache"
    )
    assert result["complete"] == 3
    features = pd.read_csv(tmp_path / "cohort" / "features.csv")
    assert set(features.run) == {4, 8, 12}
    assert features.groupby(["subject", "run", "recording"]).ngroups == 3
    coverage = pd.read_csv(tmp_path / "cohort" / "coverage.csv")
    assert set(coverage.fs_hz) == {160}
