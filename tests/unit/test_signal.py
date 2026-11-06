import numpy as np
import pytest

from soma.core.signal import Signal
from soma.signal.spectral import WelchConfig, welch
from soma.signal.synthetic import synthetic


def test_borrow_and_times():
    x = np.arange(5, dtype=float)
    sig = Signal(x, 2, t0=3)
    assert np.shares_memory(sig.values, x)
    np.testing.assert_array_equal(sig.times, [3, 3.5, 4, 4.5, 5])


@pytest.mark.parametrize(
    "data", [[], [1], [[1, 2]], [1, np.nan], [np.inf, 0], [1 + 2j, 0], [0, -np.inf]]
)
def test_invalid_data(data):
    with pytest.raises(ValueError):
        Signal(np.asarray(data), 160)


@pytest.mark.parametrize("fs", [0, -1, np.nan, np.inf])
def test_invalid_fs(fs):
    with pytest.raises(ValueError):
        Signal(np.ones(8), fs)


@pytest.mark.parametrize(
    "cfg",
    [
        WelchConfig(1, 0),
        WelchConfig(10000, 0),
        WelchConfig(320, -1),
        WelchConfig(320, 320),
        WelchConfig(320, 0, average="invalid"),
    ],
)
def test_invalid_welch(cfg):
    with pytest.raises(ValueError):
        welch(synthetic("sine10"), cfg)


@pytest.mark.parametrize("band", [(-1, 10), (10, 81), (20, 10), (10, 10), (np.nan, 10)])
def test_invalid_band(band):
    with pytest.raises(ValueError):
        welch(synthetic("sine10")).band_power(*band)


@pytest.mark.parametrize(
    "kwargs", [{"fs": 40}, {"fs": 0}, {"duration": 0}, {"duration": np.inf}, {"kind": "unknown"}]
)
def test_invalid_synthetic(kwargs):
    with pytest.raises(ValueError):
        synthetic(**({"kind": "sine10"} | kwargs))


def test_mutated_nonfinite():
    sig = synthetic("sine10")
    sig.values[0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        welch(sig)


def test_complex_rejected():
    with pytest.raises(ValueError, match="real-valued"):
        Signal(np.array([1 + 2j, 3]), 160)
