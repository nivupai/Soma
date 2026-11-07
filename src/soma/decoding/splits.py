"""Auditable outer/inner membership with event, interval and group isolation."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.model_selection import GroupKFold

from soma.decoding.config import digest
from soma.decoding.data import TrialDataset


@dataclass(frozen=True)
class Fold:
    name: str
    train: NDArray[np.int64]
    test: NDArray[np.int64]
    mode: str


def validate_split(dataset: TrialDataset, fold: Fold) -> dict[str, Any]:
    a, b = np.asarray(fold.train), np.asarray(fold.test)
    if (
        a.ndim != 1
        or b.ndim != 1
        or not len(a)
        or not len(b)
        or a.dtype.kind not in "iu"
        or b.dtype.kind not in "iu"
        or len(np.unique(a)) != len(a)
        or len(np.unique(b)) != len(b)
        or min(np.min(a), np.min(b)) < 0
        or max(np.max(a), np.max(b)) >= len(dataset.y)
        or np.intersect1d(a, b).size
    ):
        raise ValueError("Invalid, duplicated or overlapping train/test indices")
    train, test = dataset.metadata.iloc[a], dataset.metadata.iloc[b]
    if set(train.trial_id) & set(test.trial_id):
        raise ValueError("Training/test trial IDs overlap")
    if fold.mode == "cross-subject" and set(train.subject) & set(test.subject):
        raise ValueError("Cross-subject training/test participant overlap")
    if fold.mode == "within-subject":
        if (
            train.subject.nunique() != 1
            or test.subject.nunique() != 1
            or set(train.subject) != set(test.subject)
        ):
            raise ValueError("Within-subject partitions must identify the same single subject")
        if train.run.nunique() != 2 or test.run.nunique() != 1:
            raise ValueError("Within-subject decoding needs two training runs and one test run")
        if set(train.run) & set(test.run):
            raise ValueError("Held-out run overlaps training runs")
    if fold.mode == "adaptation":
        shared = set(train.subject) & set(test.subject)
        calibration = train[train.subject.isin(shared)]
        if not calibration.run.eq(4).all() or test.run.eq(4).any():
            raise ValueError("Adaptation labels must be run 4; evaluation must be other runs")
    if fold.mode not in ("cross-subject", "within-subject", "adaptation"):
        raise ValueError("Unsupported split mode")
    # Independent event identity and absolute interval checks, beyond numerical row indices.
    for key, rows in train.groupby(["subject", "run", "recording"]):
        other = test[(test.subject == key[0]) & (test.run == key[1]) & (test.recording == key[2])]
        if set(rows.event_id) & set(other.event_id):
            raise ValueError("Repeated windows from an event cross the split")
        for row in other.itertuples():
            if (
                (rows.start_sample < row.stop_sample) & (rows.stop_sample > row.start_sample)
            ).any():
                raise ValueError("Overlapping raw windows cross training/test partitions")
    ids = {"train": train.trial_id.tolist(), "test": test.trial_id.tolist()}
    return {
        "name": fold.name,
        "mode": fold.mode,
        "membership_sha256": digest(ids),
        "train_subjects": sorted(map(int, train.subject.unique())),
        "test_subjects": sorted(map(int, test.subject.unique())),
        "train_runs": sorted(map(int, train.run.unique())),
        "test_runs": sorted(map(int, test.run.unique())),
        **ids,
    }


def outer_splits(dataset: TrialDataset, mode: str, n_splits: int = 5) -> list[Fold]:
    result = []
    metadata = dataset.metadata
    if mode == "within-subject":
        for subject in sorted(metadata.subject.unique()):
            for run in (4, 8, 12):
                train = np.flatnonzero((metadata.subject == subject) & (metadata.run != run))
                test = np.flatnonzero((metadata.subject == subject) & (metadata.run == run))
                result.append(Fold(f"S{subject:03d}-R{run:02d}", train, test, mode))
    elif mode == "cross-subject":
        if metadata.subject.nunique() < n_splits:
            raise ValueError("Insufficient subjects for the prespecified grouped outer folds")
        for i, (train, test) in enumerate(
            GroupKFold(n_splits).split(dataset.X, dataset.y, groups=metadata.subject.to_numpy())
        ):
            result.append(Fold(f"subjects-{i:02d}", train, test, mode))
    else:
        raise ValueError("Use within-subject or cross-subject outer splitting")
    # Planned missing-run cells are validated and retained as failures by the engine.
    return result


def inner_splits(
    dataset: TrialDataset, training: NDArray[np.int64], n_splits: int = 3
) -> list[Fold]:
    subjects = dataset.metadata.iloc[training].subject.to_numpy()
    if len(np.unique(subjects)) < n_splits:
        raise ValueError("Insufficient training subjects for grouped inner selection")
    return [
        Fold(f"inner-{i}", training[a], training[b], "cross-subject")
        for i, (a, b) in enumerate(GroupKFold(n_splits).split(training, groups=subjects))
    ]
