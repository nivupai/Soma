import numpy as np
import pytest
from scipy.signal import welch as scipy_welch

from soma.core.signal import Signal
from soma.signal.spectral import Spectrum, WelchConfig, welch
from soma.signal.synthetic import KINDS, synthetic


@pytest.mark.parametrize("fs", [100, 160, 256])
@pytest.mark.parametrize("duration", [4, 10, 23])
@pytest.mark.parametrize(
    "kind,frequency,power", [("sine10", 10, 5e-11), ("sine20", 20, 5e-11), ("combined", 10, 1e-10)]
)
def test_tones_parseval(fs, duration, kind, frequency, power):
    sig = synthetic(kind, fs, duration)
    spec = welch(sig, WelchConfig(2 * fs, fs))
    peaks = (
        [spec.peak_frequency]
        if kind != "combined"
        else [
            spec.frequencies[np.argmax(spec.density[(spec.frequencies < 15)])],
            spec.frequencies[
                np.flatnonzero(spec.frequencies >= 15)[0]
                + np.argmax(spec.density[spec.frequencies >= 15])
            ],
        ]
    )
    assert abs(peaks[0] - frequency) <= fs / (2 * fs)
    if kind == "combined":
        assert abs(peaks[1] - 20) <= 0.5
    assert spec.band_power(0, fs / 2) == pytest.approx(power, rel=1e-10)
    assert np.mean(sig.values**2) == pytest.approx(power, rel=1e-10)


@pytest.mark.parametrize("kind", KINDS)
def test_seed_and_scipy_agreement(kind):
    sig = synthetic(kind)
    np.testing.assert_array_equal(sig.values, synthetic(kind).values)
    spec = welch(sig)
    f, p = scipy_welch(sig.values, sig.fs, nperseg=320, noverlap=160)
    np.testing.assert_array_equal(spec.frequencies, f)
    np.testing.assert_allclose(spec.density, p, rtol=1e-12, atol=1e-30)
    assert np.isfinite(spec.density).all()
    assert np.all(spec.density >= 0)


@pytest.mark.parametrize("kind", ["noisy", "modulated", "burst"])
def test_nonstationary_and_noise_power(kind):
    sig = synthetic(kind, duration=60)
    spec = welch(sig)
    assert abs(spec.peak_frequency - 10) <= 0.5
    # Overlapping Hann weighting and per-segment mean removal: 10% tolerance.
    assert spec.band_power(0, 80) == pytest.approx(np.mean(sig.values**2), rel=0.1)


def test_exact_windowed_parseval():
    rng = np.random.default_rng(17)
    x = rng.normal(size=1024)
    spec = welch(Signal(x, 256), WelchConfig(1024, 0, window="boxcar"))
    # Parseval is a bin sum, not a trapezoid at DC/Nyquist endpoints.
    assert spec.density.sum() * 0.25 == pytest.approx(np.var(x), rel=1e-12)


def test_band_boundaries_and_units():
    spec = Spectrum(np.array([0.0, 1.0, 2.0, 3.0]), np.full(4, 2.0), {})
    assert spec.band_power(0.25, 2.75) == pytest.approx(5)
    tone = welch(synthetic("sine10"))
    assert tone.band_power(8, 13) == pytest.approx(5e-11, rel=1e-10)
    assert tone.band_power(13, 30) < 1e-25
    assert tone.metadata["units"] == "V^2/Hz"


def test_nyquist_odd_segment_and_resolution():
    sig = synthetic("sine10", fs=160)
    a, b = welch(sig, WelchConfig(160, 0)), welch(sig, WelchConfig(320, 0))
    assert a.frequencies[1] == 1
    assert b.frequencies[1] == 0.5
    odd = welch(sig, WelchConfig(319, 0))
    assert odd.frequencies[-1] < 80
    with pytest.raises(ValueError):
        odd.band_power(0, 80)


def test_median_is_neurodsp_raw_median():
    from neurodsp.spectral import compute_spectrum_welch

    sig = synthetic("noisy")
    result = welch(sig, WelchConfig(320, 160, average="median"))
    _, expected = compute_spectrum_welch(
        sig.values, sig.fs, avg_type="median", nperseg=320, noverlap=160
    )
    np.testing.assert_array_equal(result.density, expected)
