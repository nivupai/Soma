"""Measured motion/physiology policies with full-grid spikes and explicit exclusions."""

from dataclasses import replace
from typing import Any

import numpy as np

from soma.fmri.design import ModelConfig, build_design
from soma.fmri.records import FunctionalRun

MOTION = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z")


def configure_confounds(
    run: FunctionalRun,
    metadata: dict[str, Any],
    *,
    strategy: str = "minimal",
    config: ModelConfig | None = None,
) -> tuple[ModelConfig, dict[str, Any]]:
    if strategy not in {"minimal", "expanded", "compcor", "fd-spikes"}:
        raise ValueError("Unsupported confound strategy")
    columns = list(MOTION)
    if strategy == "compcor":
        available = [
            c
            for c in map(str, run.confounds.columns)
            if c.startswith("a_comp_cor_") and metadata.get(c, {}).get("Retained") is True
        ]
        if not available:
            raise ValueError(
                "Requested physiological nuisance requires explicitly retained CompCor columns"
            )
        columns += sorted(available)[:6]
    if strategy == "fd-spikes":
        columns += [
            c for c in map(str, run.confounds.columns) if c.startswith("non_steady_state_outlier")
        ]
    for name in columns:
        if name.startswith("non_steady_state_outlier"):
            values = run.confounds[name].to_numpy(float)
            if not np.isin(values, [0, 1]).all() or values.sum() != 1:
                raise ValueError("Nonsteady-state indicators must be binary one-hot columns")
    for name in [*columns, "framewise_displacement"]:
        if name not in run.confounds:
            raise ValueError(f"Missing measured confound: {name}")
        if not isinstance(metadata.get(name), dict) or not any(
            metadata[name].get(k) for k in ["Description", "LongName", "Method"]
        ):
            raise ValueError(f"Missing confound definition: {name}")
    for name in MOTION:
        units = metadata[name].get("Units")
        if units != ("mm" if name.startswith("trans_") else "rad"):
            raise ValueError("Motion units require mm translations and rad rotations")
    if metadata["framewise_displacement"].get("Units") != "mm":
        raise ValueError("FD units must be mm")
    fd = run.confounds.framewise_displacement.to_numpy(float).copy()
    first_missing = bool(np.isnan(fd[0]))
    if first_missing:
        fd[0] = 0
    if not np.isfinite(fd).all() or np.any(fd < 0):
        raise ValueError("Invalid FD; only undefined first sample may become0")
    high = fd > 0.5
    reasons = []
    if fd.mean() > 0.5:
        reasons.append("mean FD exceeds0.5mm")
    if high.mean() > 0.2:
        reasons.append("more than20% high-motion frames")
    cfg = replace(
        config or ModelConfig(),
        confound_columns=tuple(columns),
        motion_derivatives=strategy == "expanded",
        fd_threshold=0.5 if strategy == "fd-spikes" else None,
    )
    design, diagnostics = build_design(run, cfg)
    if diagnostics["residual_dof"] < 20:
        reasons.append("residual degrees of freedom below20")
    dvars = None
    if "dvars" in run.confounds:
        values = run.confounds.dvars.to_numpy(float)
        finite = values[np.isfinite(values)]
        dvars = {
            "available": True,
            "mean": float(finite.mean()) if len(finite) else None,
            "undefined": int(np.sum(~np.isfinite(values))),
        }
    spike_names = [
        c
        for c in map(str, design.columns)
        if c.startswith("spike_") or c.startswith("non_steady_state_outlier")
    ]
    return cfg, {
        "strategy": strategy,
        "columns": columns,
        "generated_motion_derivatives": strategy == "expanded",
        "mean_FD_mm": float(fd.mean()),
        "max_FD_mm": float(fd.max()),
        "p95_FD_mm": float(np.quantile(fd, 0.95)),
        "high_motion_frames": int(high.sum()),
        "high_motion_fraction": float(high.mean()),
        "first_FD_missing_policy_applied": first_missing,
        "DVARS": dvars,
        "spike_columns": spike_names,
        "acquired_observations": run.n_scans,
        "deleted_observations": 0,
        "unspiked_observations": run.n_scans - len(spike_names),
        "design": diagnostics,
        "eligible": not reasons,
        "exclusion_reasons": reasons,
        "inference_limit": "spikes change rank/DOF; acquisition grid and noise adjacency retained",
    }
