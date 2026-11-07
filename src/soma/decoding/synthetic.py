"""Known oscillatory mixtures with independently controlled labels and group shifts."""

from typing import Any

import numpy as np

from soma.decoding.data import TrialDataset

CHANNELS = ("FC3", "FCz", "FC4", "C3", "Cz", "C4", "CP3", "CPz", "CP4")


def simulate_decoding(
    seed: int = 42,
    n_subjects: int = 6,
    n_trials: int = 16,
    effect: float = 0.8,
    noise: float = 0.3,
    subject_shift: float = 0.05,
    run_drift: float = 0.02,
    rank_deficient: bool = False,
    right_fraction: float = 0.5,
    null: bool = False,
) -> tuple[TrialDataset, dict[str, Any]]:
    if (
        seed < 0
        or n_subjects < 2
        or n_trials < 6
        or not 0 <= effect < 1
        or noise < 0
        or subject_shift < 0
        or run_drift < 0
        or not 0 < right_fraction < 1
    ):
        raise ValueError("Invalid synthetic mixture parameters")
    import pandas as pd

    rng = np.random.default_rng(seed)
    fs, scale = 160.0, 20e-6
    times = np.arange(640) / fs
    frequencies = np.asarray([10.0, 20.0, 12.0, 15.0, 18.0, 22.0, 25.0, 28.0, 8.0])
    base = np.linalg.qr(rng.normal(size=(9, 9)))[0]
    arrays, labels, rows, mixing = [], [], [], {}
    for subject in range(1, n_subjects + 1):
        individual = base + subject_shift * rng.normal(size=base.shape)
        if rank_deficient:
            individual[-1] = individual[0] + individual[1]
        mixing[str(subject)] = individual.tolist()
        for run in (4, 8, 12):
            count = n_trials + (run // 4 - 1) * 2
            right = max(1, min(count - 1, round(count * right_fraction)))
            latent = rng.permutation(
                np.r_[np.zeros(count - right, dtype=int), np.ones(right, dtype=int)]
            )
            observed = (
                rng.permutation(
                    np.r_[np.zeros(count - right, dtype=int), np.ones(right, dtype=int)]
                )
                if null
                else latent
            )
            run_mix = individual * (1 + run_drift * (run / 4 - 2))
            for trial, (condition, label) in enumerate(zip(latent, observed, strict=True)):
                amplitude = np.full(9, 0.4)
                amplitude[:2] = np.sqrt(
                    [1 + effect * (2 * condition - 1), 1 - effect * (2 * condition - 1)]
                )
                sources = (
                    amplitude[:, None]
                    * np.sqrt(2)
                    * np.sin(
                        2 * np.pi * frequencies[:, None] * times + rng.uniform(0, 2 * np.pi, (9, 1))
                    )
                )
                sensor_noise = (
                    noise * (1 + subject / (10 * n_subjects)) * rng.normal(size=sources.shape)
                )
                context = scale * (run_mix @ (sources + sensor_noise))
                arrays.append(context)
                labels.append(label)
                rows.append(
                    dict(
                        subject=subject,
                        run=run,
                        recording=f"synthetic-S{subject}R{run}",
                        event_id=trial,
                        trial_id=f"synthetic-S{subject}R{run}E{trial}",
                        label=int(label),
                        start_sample=round((trial * 5 + 1) * fs),
                        stop_sample=round((trial * 5 + 3) * fs),
                        qc_accepted=True,
                        preprocessing_fingerprint="synthetic-known-mixture-v1",
                    )
                )
    context = np.asarray(arrays)
    truth = {
        "seed": seed,
        "base_mixing": base.tolist(),
        "subject_mixing": mixing,
        "frequencies_hz": frequencies.tolist(),
        "effect": effect,
        "noise": noise,
        "subject_shift": subject_shift,
        "run_drift": run_drift,
        "null": null,
        "rank_deficient": rank_deficient,
        "scale_v": scale,
        "model": "random-phase oscillators; class-dependent source variances; "
        "subject/run mixing; mixed noise",
    }
    dataset = TrialDataset(
        context[:, :, 160:480].copy(),
        np.asarray(labels, dtype=np.int64),
        pd.DataFrame(rows),
        CHANNELS,
        fs,
        (1.0, 3.0),
        context,
        (0.0, 4.0),
        {"synthetic": truth},
    )
    return dataset, truth
