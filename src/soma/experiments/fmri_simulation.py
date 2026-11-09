"""Seeded 4D laboratory with independent high-resolution HRF convolution."""

from dataclasses import replace
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
from scipy.stats import gamma

from soma.fmri.records import FunctionalRun
from soma.imaging.volumes import Volume


def canonical_response(
    times: np.ndarray[Any, Any], events: pd.DataFrame, *, delay: float = 0.0
) -> np.ndarray[Any, Any]:
    """Independent gamma-difference SPM HRF quadrature, 0.01s grid, causal convolution."""
    step = 0.01
    dense = np.arange(0, float(times[-1]) + 32 + step, step)
    stimulus = np.zeros_like(dense)
    for row in events.to_dict("records"):
        if row["trial_type"] != "task":
            continue
        start = int(round((float(row["onset"]) + delay) / step))
        stop = int(round((float(row["onset"]) + delay + float(row["duration"])) / step))
        if start < 0:
            raise ValueError("Simulation delayed onset precedes time zero")
        stimulus[start : max(stop, start + 1)] += 1
    htimes = np.arange(0, 32, step)
    hrf = gamma.pdf(htimes, 6) - gamma.pdf(htimes, 16) / 6
    hrf /= hrf.sum()
    from scipy.signal import fftconvolve

    response = fftconvolve(stimulus, hrf)[: len(dense)]
    return np.asarray(np.interp(times, dense, response))


def simulate(
    seed: int = 13042,
    *,
    tr: float = 2.0,
    n_scans: int = 100,
    beta: float = 3.0,
    noise: float = 0.5,
    ar: float = 0.0,
    spatial_sigma: float = 0.0,
    hrf_delay: float = 0.0,
    session: str = "development",
) -> tuple[FunctionalRun, dict[str, Any]]:
    if not 0 <= ar < 1 or noise < 0 or tr <= 0 or n_scans < 40 or spatial_sigma < 0:
        raise ValueError("Invalid synthetic noise/timing parameters")
    rng = np.random.default_rng(seed)
    shape = (7, 7, 7)
    onset = np.arange(10, n_scans * tr - 25, 30)
    events = pd.DataFrame({"onset": onset, "duration": 6.0, "trial_type": "task"})
    time = np.arange(n_scans) * tr
    response = canonical_response(time, events, delay=hrf_delay)
    xyz = np.indices(shape)
    region = (xyz[0] <= 2) & (xyz[1] >= 2) & (xyz[1] <= 4) & (xyz[2] >= 2) & (xyz[2] <= 4)
    negative = (xyz[0] >= 4) & (xyz[1] >= 2) & (xyz[1] <= 4) & (xyz[2] >= 2) & (xyz[2] <= 4)
    effects = beta * (region.astype(float) - negative.astype(float))
    motion = np.sin(time * 0.19) + rng.normal(0, 0.2, n_scans)
    trend = (time - time.mean()) / max(float(np.max(time)), 1)
    errors = rng.normal(0, noise, (*shape, n_scans))
    if spatial_sigma:
        errors = gaussian_filter(errors, (spatial_sigma, spatial_sigma, spatial_sigma, 0))
    for i in range(1, n_scans):
        errors[..., i] = ar * errors[..., i - 1] + errors[..., i]
    data = 100 + effects[..., None] * response + 0.3 * motion + 2 * trend + errors
    affine = np.diag([3.0, 3.0, 3.0, 1.0])
    affine[:3, 3] = -9
    image = nib.Nifti1Image(data.astype(np.float32), affine)
    image.header.set_xyzt_units("mm", "sec")
    image.header.set_zooms((3, 3, 3, tr))
    mask = Volume(np.ones(shape, np.uint8), affine * np.array([0.001] * 3 + [1])[:, None], "labels")
    run = FunctionalRun(
        image,
        tr,
        "synthetic",
        session,
        "task",
        "1",
        "synthetic-RAS",
        events,
        pd.DataFrame({"motion": motion, "trend": trend}),
        mask,
        "synthetic",
        {
            "source": "entirely synthetic",
            "effect_scale_identity": "synthetic-native-units-v1",
            "seed": seed,
            "cross_session_alignment": "identical analytic grid",
        },
    )
    truth = {
        "beta": effects,
        "positive": region,
        "negative": negative,
        "response": response,
        "noise": noise,
        "ar": ar,
        "spatial_sigma": spatial_sigma,
        "hrf_delay_s": hrf_delay,
        "seed": seed,
        "tr": tr,
    }
    return run, truth


def second_visit(run: FunctionalRun, session: str) -> FunctionalRun:
    return replace(run, session=session)
