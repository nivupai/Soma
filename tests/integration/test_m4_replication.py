import os
from pathlib import Path

import pandas as pd
import pytest

from soma.datasets.eegbci import recording_path
from soma.experiments.replication import replicate

pytestmark = pytest.mark.integration


def test_cached_new_subject_replication_resume(tmp_path):
    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not all(recording_path(root, 6, run).is_file() for run in (4, 8)):
        pytest.skip("Explicitly fetch subject 6 runs 4 and 8; no test downloads")
    output = tmp_path / "real"
    result = replicate(
        root,
        output,
        Path("configs/replication.yaml"),
        subjects=(6,),
        runs=(4, 8),
        cache_root=tmp_path / "cache",
        plots=False,
        initial=None,
    )
    assert result["complete"] == 2
    result = replicate(
        root,
        output,
        Path("configs/replication.yaml"),
        subjects=(6,),
        runs=(4, 8),
        cache_root=tmp_path / "cache",
        plots=False,
        initial=None,
        resume=True,
    )
    assert result["resumed"] == 2
    subjects = pd.read_csv(Path(result["generation"]) / "subject_contrasts.csv")
    assert subjects.included.all()
    population = pd.read_csv(Path(result["generation"]) / "population.csv")
    assert population.n_subjects.eq(1).all()
    assert population.ci_low.isna().all()
