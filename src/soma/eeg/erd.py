"""Explicitly aligned power references and masked normalization; no epsilon repair."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class PowerCoordinates:
    channels: tuple[str, ...]
    frequencies: tuple[float | str, ...]  # frequency centers or named bands


@dataclass(frozen=True)
class PowerChange:
    percent: NDArray[np.float64]
    log_ratio: NDArray[np.float64]  # natural logarithm
    difference: NDArray[np.float64]
    valid: NDArray[np.bool_]


def power_change(
    power: NDArray[np.float64],
    reference: NDArray[np.float64],
    coordinates: PowerCoordinates,
    reference_coordinates: PowerCoordinates,
    minimum_reference: float = 0.0,
) -> PowerChange:
    """Inputs have identical T×C×F[×time] shape; broadcast references explicitly.

    minimum_reference has the same units as input power. Invalid denominators
    and unsupported references are masked with NaN, without epsilon substitution.
    Absolute differences remain available where inputs are finite and nonnegative.
    """
    if coordinates != reference_coordinates or power.shape != reference.shape:
        raise ValueError("Power/reference coordinates and shapes must match exactly")
    if power.ndim not in (3, 4) or power.shape[1:3] != (
        len(coordinates.channels),
        len(coordinates.frequencies),
    ):
        raise ValueError("Expected trial×channel×frequency[×time] power")
    if not np.isfinite(minimum_reference) or minimum_reference < 0:
        raise ValueError("Reference floor must be finite and nonnegative in power units")
    if np.any(power[np.isfinite(power)] < 0) or np.any(reference[np.isfinite(reference)] < 0):
        raise ValueError("Power must be nonnegative")
    finite = np.isfinite(power) & np.isfinite(reference)
    valid = finite & (reference > minimum_reference)
    ratio = np.full(power.shape, np.nan)
    np.divide(power, reference, out=ratio, where=valid)
    percent = np.where(valid, 100 * (ratio - 1), np.nan)
    log_ratio = np.full(power.shape, np.nan)
    np.log(ratio, out=log_ratio, where=valid & (ratio > 0))
    # log(0) is unavailable rather than a silently injected positive number.
    difference = np.where(finite, power - reference, np.nan)
    return PowerChange(percent, log_ratio, difference, valid)


def lateralization(c3: NDArray[np.float64], c4: NDArray[np.float64]) -> NDArray[np.float64]:
    """(C4 − C3)/(C4 + C3): positive means more C3 suppression in power input."""
    if c3.shape != c4.shape:
        raise ValueError("C3/C4 dimensions must match")
    if np.any(c3 < 0) or np.any(c4 < 0):
        raise ValueError("Lateralization requires nonnegative absolute power")
    denominator = c4 + c3
    result = np.full(c3.shape, np.nan)
    np.divide(c4 - c3, denominator, out=result, where=np.isfinite(denominator) & (denominator > 0))
    return result
