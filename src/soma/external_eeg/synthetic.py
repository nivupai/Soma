"""Independent fictional session recordings; no copied target trials or human labels."""

import numpy as np
import pandas as pd

from soma.decoding.data import TrialDataset
from soma.external_eeg.contracts import CHANNELS, feature_contract
from soma.workflow.model import digest


def fictional(seed: int = 23042) -> TrialDataset:
    rng = np.random.default_rng(seed)
    signals = []
    rows = []
    time = np.arange(320) / 160
    for subject in range(1, 10):
        for session in ("T", "E"):
            for run in range(1, 7):
                for trial in range(6):
                    label = trial % 2
                    X = rng.normal(0, 2e-6, (9, 320))
                    for c in range(9):
                        X[c] += 4e-6 * np.sin(2 * np.pi * (10 + c) * time + rng.uniform(0, 6))
                    X[3] += (
                        18e-6
                        * (1 if label else 0.3)
                        * np.sin(2 * np.pi * 10 * time + rng.uniform(0, 6))
                    )
                    X[5] += (
                        18e-6
                        * (0.3 if label else 1)
                        * np.sin(2 * np.pi * 20 * time + rng.uniform(0, 6))
                    )
                    record = f"synthetic-external-v1/s{subject:02}/{session}/r{run}"
                    rows.append(
                        {
                            "subject": subject,
                            "session": session,
                            "run": run,
                            "recording": record,
                            "event_id": trial,
                            "trial_id": record + f"/t{trial}",
                            "label": label,
                            "start_sample": trial * 800,
                            "stop_sample": trial * 800 + 320,
                            "qc_accepted": True,
                            "preprocessing_fingerprint": digest(feature_contract("synthetic-nine")),
                        }
                    )
                    signals.append(X)
    data = np.asarray(signals)
    frame = pd.DataFrame(rows)
    return TrialDataset(
        data,
        frame.label.to_numpy(dtype=np.int64),
        frame,
        tuple(CHANNELS),
        160.0,
        (1.0, 3.0),
        data.copy(),
        (1.0, 3.0),
        {"dataset": "synthetic-external-v1", "contract": feature_contract("synthetic-nine")},
    )
