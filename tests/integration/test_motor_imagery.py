import os
from pathlib import Path

import pandas as pd
import pytest

from soma.datasets.eegbci import recording_path
from soma.eeg.motor_imagery import MotorImageryConfig, motor_imagery

pytestmark = pytest.mark.integration


def test_cached_motor_imagery(tmp_path):
    root = Path(os.environ.get("SOMA_DATA_DIR", "data/raw"))
    if not recording_path(root, 1, 4).is_file():
        pytest.skip("Fetch S001R04 explicitly; tests never download")
    output = tmp_path / "motor"
    result = motor_imagery(root, 1, [4], output, MotorImageryConfig(plots=False))
    events = pd.read_csv(output / "events.csv")
    assert events.code.value_counts().to_dict() == {"T0": 15, "T1": 8, "T2": 7}
    features = pd.read_csv(output / "spectral_features.csv")
    assert set(features.channel) == {"C3", "Cz", "C4"}
    assert {"left hand imagery", "right hand imagery"} <= set(features.condition)
    assert result["parameters"]["preprocessing"]["reference"] == "average"
    assert (output / "run-04" / "timefrequency.npz").is_file()
