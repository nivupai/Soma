"""Repeated log-power measurements with structural truth separate from observed target."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import norm

SCENARIOS = (
    "normal",
    "correlated_unequal",
    "heteroscedastic",
    "heavy_tail",
    "contaminated",
    "nonrandom_missing",
    "preprocessing_shift",
)


@dataclass(frozen=True)
class SimulationConfig:
    scenario: str = "correlated_unequal"
    n_subjects: int = 30
    n_runs: int = 3
    min_trials: int = 8
    max_trials: int = 24
    effect: float = 0.3
    subject_effect_sd: float = 0.4
    run_effect_sd: float = 0.2
    trial_sd: float = 0.7
    correlation: float = 0.6

    def __post_init__(self) -> None:
        if (
            self.scenario not in SCENARIOS
            or self.n_subjects < 2
            or self.n_runs < 1
            or not 1 <= self.min_trials <= self.max_trials
            or not np.isfinite(
                [
                    self.effect,
                    self.subject_effect_sd,
                    self.run_effect_sd,
                    self.trial_sd,
                    self.correlation,
                ]
            ).all()
            or min(self.subject_effect_sd, self.run_effect_sd, self.trial_sd) < 0
            or not 0 <= self.correlation <= 1
        ):
            raise ValueError("Invalid repeated-measures simulation parameters")


def simulate(cfg: SimulationConfig, seed: int) -> dict[str, Any]:
    if seed < 0:
        raise ValueError("Simulation seed must be nonnegative")
    rng = np.random.default_rng(seed)
    n, r, t = cfg.n_subjects, cfg.n_runs, cfg.max_trials
    if cfg.scenario == "normal":
        # Analytic independent-subject benchmark, separately labeled from repeated EEG model.
        effects = rng.normal(cfg.effect, cfg.subject_effect_sd, n)
        return {
            "subject_effects": effects,
            "run_effects": effects[:, None],
            "left_means": effects[:, None],
            "right_means": np.zeros((n, 1)),
            "left_counts": np.ones((n, 1), dtype=int),
            "right_counts": np.ones((n, 1), dtype=int),
            "structural_truth": cfg.effect,
            "target_mean": cfg.effect,
            "n_requested": n,
            "model": "independent normal subject effects",
        }
    subject_intercept = rng.normal(-24, 1, n)
    individual = (
        rng.standard_t(3, n) / np.sqrt(3) * cfg.subject_effect_sd
        if cfg.scenario == "heavy_tail"
        else rng.normal(0, cfg.subject_effect_sd, n)
    )
    contamination = (rng.random(n) < 0.05) * 3 if cfg.scenario == "contaminated" else np.zeros(n)
    individual_effect = cfg.effect + individual + contamination
    run_intercept = rng.normal(0, 0.5, (n, r))
    run_difference = rng.normal(0, cfg.run_effect_sd, (n, r))
    common = rng.normal(size=(n, r, 2, 1))
    independent = (
        rng.standard_t(3, (n, r, 2, t)) / np.sqrt(3)
        if cfg.scenario == "heavy_tail"
        else rng.normal(size=(n, r, 2, t))
    )
    scale = (
        cfg.trial_sd * (1 + 2 * np.abs(individual))
        if cfg.scenario == "heteroscedastic"
        else np.full(n, cfg.trial_sd)
    )
    residual = scale[:, None, None, None] * (
        np.sqrt(cfg.correlation) * common + np.sqrt(1 - cfg.correlation) * independent
    )
    shifts = np.zeros((n, r, 2, 1))
    shifts[:, :, 0, 0] = individual_effect[:, None] + run_difference
    values = (
        subject_intercept[:, None, None, None] + run_intercept[:, :, None, None] + shifts + residual
    )
    counts = rng.integers(cfg.min_trials, cfg.max_trials + 1, (n, r, 2))
    usable = np.arange(t)[None, None, None, :] < counts[:, :, :, None]
    means = np.sum(np.where(usable, values, 0), axis=-1) / counts
    differences = means[:, :, 0] - means[:, :, 1]
    target = (
        cfg.effect + 0.15 if cfg.scenario in ("contaminated", "preprocessing_shift") else cfg.effect
    )
    if cfg.scenario == "preprocessing_shift":
        differences += 0.15
        means[:, :, 0] += 0.15
    if cfg.scenario == "nonrandom_missing":
        retained = individual > -0.2
        missing_runs = rng.random((n, r)) < 0.15
        differences[~retained] = np.nan
        differences[missing_runs] = np.nan
        counts[~np.isfinite(differences)] = 0
        means[~np.isfinite(differences)] = np.nan
        # Truncated-normal retained mean; independent run loss adds no mean shift.
        threshold = -0.2 / cfg.subject_effect_sd if cfg.subject_effect_sd > 0 else -np.inf
        target = cfg.effect + cfg.subject_effect_sd * norm.pdf(threshold) / norm.sf(threshold)
    valid = np.isfinite(differences)
    subject = np.full(n, np.nan)
    np.divide(
        np.nansum(differences, axis=1), valid.sum(axis=1), out=subject, where=valid.sum(axis=1) > 0
    )
    return {
        "subject_effects": subject,
        "run_effects": differences,
        "left_means": means[:, :, 0],
        "right_means": means[:, :, 1],
        "left_counts": counts[:, :, 0],
        "right_counts": counts[:, :, 1],
        "structural_truth": cfg.effect,
        "target_mean": float(target),
        "n_requested": n,
        "individual_effects": individual_effect,
        "subject_intercepts": subject_intercept,
        "model": (
            "log power: subject/run intercepts, individual/run condition effects, correlated trials"
        ),
    }
