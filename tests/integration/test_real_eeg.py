import os
from pathlib import Path

import pytest

from soma.datasets.eegbci import load_recording, recording_path
from soma.eeg.analysis import analyze_recording

pytestmark = pytest.mark.integration


def test_cached_subject1_run4(tmp_path):
    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not recording_path(root, 1, 4).is_file():
        pytest.skip("Explicitly fetch subject 1 run 4 first; tests never download")
    raw, metadata = load_recording(root, 1, 4)
    assert metadata["n_eeg_channels"] == 64
    assert metadata["sfreq_hz"] == 160
    assert {"C3", "Cz", "C4"} <= set(raw.ch_names)
    assert {a["description"] for a in metadata["annotations"]} == {"T0", "T1", "T2"}
    raw.close()
    result = analyze_recording(root, 1, 4, tmp_path / "real")
    assert result["source"]["sha256"]
