"""Nilearn design construction with explicit timing, rank and nuisance diagnostics."""

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from nilearn.glm.first_level import make_first_level_design_matrix

from soma.fmri.records import FunctionalRun


@dataclass(frozen=True)
class ModelConfig:
    hrf_model: str = "spm"
    drift_model: str | None = "cosine"
    high_pass: float = 1 / 128
    slice_time_ref: float = 0.0
    noise_model: str = "ar1"
    smoothing_fwhm: float = 0.0
    confound_columns: tuple[str, ...] = ()
    motion_derivatives: bool = False
    fd_threshold: float | None = None
    initial_spikes: int = 0
    q: float = 0.05

    def __post_init__(self) -> None:
        if self.hrf_model not in {"spm", "spm + derivative", "glover", "glover + derivative"}:
            raise ValueError("Unsupported HRF model")
        if self.drift_model not in {None, "cosine", "polynomial"}:
            raise ValueError("Unsupported drift model")
        if self.noise_model not in {"ols", "ar1"}:
            raise ValueError("Noise model must be OLS or feasible AR(1)")
        numbers = [self.high_pass, self.slice_time_ref, self.smoothing_fwhm, self.q]
        if (
            not np.isfinite(numbers).all()
            or not 0 <= self.slice_time_ref <= 1
            or self.high_pass <= 0
        ):
            raise ValueError("Invalid finite temporal model parameters")
        if (
            not isinstance(self.initial_spikes, int)
            or self.smoothing_fwhm < 0
            or not 0 < self.q < 1
            or self.initial_spikes < 0
        ):
            raise ValueError("Invalid smoothing, FDR q or spike count")
        if self.fd_threshold is not None and (
            not np.isfinite(self.fd_threshold) or self.fd_threshold <= 0
        ):
            raise ValueError("FD threshold must be positive millimetres")


def nuisance(run: FunctionalRun, config: ModelConfig) -> pd.DataFrame:
    missing = set(config.confound_columns) - set(run.confounds.columns)
    if missing:
        raise ValueError(f"Missing requested confound columns: {sorted(missing)}")
    result = run.confounds.loc[:, list(config.confound_columns)].astype(float).copy()
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError("Selected confounds are nonfinite; no implicit imputation")
    if config.motion_derivatives:
        for name in config.confound_columns:
            if name + "_derivative" in result:
                raise ValueError("Motion derivative confound name collision")
            result[name + "_derivative"] = np.r_[0.0, np.diff(result[name])]
    indices = set(range(config.initial_spikes))
    if config.fd_threshold is not None:
        if "framewise_displacement" not in run.confounds:
            raise ValueError("FD censoring requires measured framewise_displacement")
        fd = run.confounds["framewise_displacement"].to_numpy(dtype=float).copy()
        if np.isnan(fd[0]):
            fd[0] = 0.0  # first displacement is undefined by construction, logged below
        if not np.isfinite(fd).all() or np.any(fd < 0):
            raise ValueError("FD must be finite/nonnegative except undefined first sample")
        indices.update(np.flatnonzero(fd > config.fd_threshold).tolist())
    if any(i >= run.n_scans for i in indices):
        raise ValueError("Spike count exceeds available volumes")
    for index in sorted(indices):
        if f"spike_{index:04}" in result:
            raise ValueError("Spike confound name collision")
        result[f"spike_{index:04}"] = (np.arange(run.n_scans) == index).astype(float)
    return result


def validate_events(events: pd.DataFrame, n_scans: int, tr: float) -> None:
    if not {"onset", "duration", "trial_type"}.issubset(events) or events.empty:
        raise ValueError("Events require onset, duration and trial_type")
    times = events[["onset", "duration"]].to_numpy(dtype=float)
    if not np.isfinite(times).all() or np.any(times < 0):
        raise ValueError("Event times/durations must be finite and nonnegative")
    if np.any(times[:, 0] >= n_scans * tr) or np.any(times.sum(axis=1) > n_scans * tr):
        raise ValueError("Events fall outside acquisition coverage")
    if events.trial_type.isna().any() or any(
        not isinstance(t, str) or not t for t in events.trial_type
    ):
        raise ValueError("Nonempty condition names required")
    if "modulation" in events and not np.isfinite(events.modulation.to_numpy(float)).all():
        raise ValueError("Event modulation must be finite")


def diagnostics(design: pd.DataFrame) -> dict[str, Any]:
    x = design.to_numpy(dtype=float)
    if not np.isfinite(x).all() or design.columns.duplicated().any():
        raise ValueError("Design requires unique names and finite values")
    rank = int(np.linalg.matrix_rank(x))
    condition = float(np.linalg.cond(x))
    dof = len(x) - rank
    if rank != x.shape[1] or dof <= 0 or condition > 1e10:
        raise ValueError("Rank-deficient/ill-conditioned design or nonpositive residual DOF")
    centered = x - x.mean(axis=0)
    norms = np.linalg.norm(centered, axis=0)
    varying = norms > 1e-12
    normalized = centered[:, varying] / norms[varying]
    correlation = normalized.T @ normalized
    offdiag = correlation - np.eye(len(correlation))
    return {
        "names": list(design.columns),
        "samples": len(x),
        "rank": rank,
        "residual_dof": dof,
        "condition_number": condition,
        "max_absolute_regressor_correlation": float(np.max(np.abs(offdiag), initial=0)),
        "varying_names": list(design.columns[varying]),
        "correlation": correlation.tolist(),
    }


def build_design(run: FunctionalRun, config: ModelConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    validate_events(run.events, run.n_scans, run.tr)
    if config.high_pass >= 1 / (2 * run.tr):
        raise ValueError("High-pass frequency must be below Nyquist")
    confounds = nuisance(run, config)
    reserved = set(run.events.trial_type) | {"constant"}
    if reserved.intersection(confounds.columns) or confounds.columns.duplicated().any():
        raise ValueError("Confound names collide with task/intercept")
    frame_times = (np.arange(run.n_scans) + config.slice_time_ref) * run.tr
    # Nilearn regularizes singular X; inspect its resulting condition number and
    # reject its epsilon-regularized singular matrices rather than silently fit.
    design = make_first_level_design_matrix(
        frame_times,
        run.events[
            [c for c in ["onset", "duration", "trial_type", "modulation"] if c in run.events]
        ],
        hrf_model=config.hrf_model,
        drift_model=config.drift_model,
        high_pass=config.high_pass,
        add_regs=None if confounds.empty else confounds.to_numpy(),
        add_reg_names=None if confounds.empty else list(confounds.columns),
    )
    report = diagnostics(design)
    report.update(
        {
            "frame_times_s": frame_times.tolist(),
            "hrf_model": config.hrf_model,
            "drift_model": config.drift_model,
            "high_pass_Hz": config.high_pass,
            "event_counts": run.events.trial_type.value_counts().to_dict(),
            "confounds": list(confounds),
            "deleted_volumes": 0,
            "fd_first_missing_policy": "first undefined displacement=0 only",
            "drift_order": 1,
            "oversampling": 50,
        }
    )
    return design, report


@dataclass(frozen=True)
class Contrast:
    name: str
    weights: dict[str, float] | tuple[float, ...]
    tail: str = "two-sided"

    def vector(self, design: pd.DataFrame) -> np.ndarray[Any, Any]:
        if not re.fullmatch(r"[A-Za-z0-9-]+", self.name) or self.tail != "two-sided":
            raise ValueError("Named two-sided signed t contrast required")
        if isinstance(self.weights, dict):
            if not self.weights or set(self.weights) - set(design.columns):
                raise ValueError("Contrast condition missing from actual design")
            c = np.array([self.weights.get(name, 0.0) for name in design.columns])
        else:
            c = np.asarray(self.weights, dtype=float)
        if c.shape != (design.shape[1],) or not np.isfinite(c).all() or not np.any(c):
            raise ValueError("Contrast vector has invalid dimension/nonfinite/zero weights")
        x = design.to_numpy()
        if not np.allclose(c @ np.linalg.pinv(x) @ x, c, atol=1e-9):
            raise ValueError("Contrast is not estimable")
        return c
