# Signal and spectral mathematics

A real signal x[n], n=0,...,N−1, has equally spaced samples at
`t[n] = t0 + n/fs`, in seconds; fs is positive and measured in Hz. EEG values are
volts, not microvolts. A plot may multiply by 10^6 and explicitly label µV.
No missing-sample interpolation or sample deletion is performed: these would
change the signal and time axis. NaN, infinity and non-1D inputs are errors.
Real-valued input is required. Sampling must be uniform; timestamps are implied.

The unnormalized discrete Fourier transform and inverse are

```math
X[k] = \sum_{n=0}^{N-1} x[n] e^{-2\pi i kn/N},\qquad
x[n] = \frac{1}{N}\sum_{k=0}^{N-1}X[k] e^{2\pi i kn/N}.
```

Parseval under this convention is

```math
\frac{1}{N}\sum_n |x[n]|^2 = \frac{1}{N^2}\sum_k |X[k]|^2.
```

The left side is mean-square power (V²), not energy and not PSD. Subtracting a
constant mean yields variance; a zero-mean sinusoid A sin(2πft) containing integer
cycles has mean-square A²/2. This voltage-squared measure is not watts without
an impedance model.

For a length-L segment, remove its arithmetic mean, then multiply by window w[n].
With `U = sum(w[n]^2)`, its two-sided modified periodogram is

```math
P_j[k] = \frac{|\operatorname{DFT}(w\,x_j)[k]|^2}{f_s U}.
```

For real input, fold the negative frequencies onto the positive frequencies:
double interior bins, leaving DC and (for even L) Nyquist undoubled. Units are
V²/Hz. Welch's estimate is the arithmetic mean of these segment densities:

```math
\widehat S[k] = \frac{1}{J}\sum_{j=1}^J P_j[k].
```

Soma calls genuine NeuroDSP `compute_spectrum_welch`, which computes a SciPy
spectrogram and averages its time windows. Installed source was inspected.
Explicit parameters override NeuroDSP's default one-second segments and
one-eighth overlap. Our default is periodic Hann, L=320, overlap=160, mean
averaging, `fast_len=False`, no padding, no frequency cropping, no outlier
removal. SciPy spectrogram defaults supply constant detrending, density scaling,
and one-sided output. Offline comparison tests guard these assumptions.

`average='median'` exposes NeuroDSP's raw pointwise median. Unlike SciPy Welch's
median option, NeuroDSP does not apply a finite-sample median bias correction.
It is robust to extreme segments but is not an unbiased mean-power estimator.
Mean averaging is the baseline for power-conservation tests.

Frequency spacing is Δf=fs/L: 0.5 Hz for the default 160 Hz EEG. A longer recording
with fixed L adds averages and reduces estimator variability; it does not narrow
bin spacing. Increasing L narrows bin spacing at the cost of fewer averages and
poorer temporal localization. Zero padding can create denser bins without
improving physical resolution; it is deliberately absent from this initial API
because NeuroDSP's `window_pad` also changes the window construction.

A finite record multiplies the underlying infinite signal by a window. In the
frequency domain this convolves its spectrum with the window transform, spreading
power away from an off-bin tone (spectral leakage). Hann reduces sidelobes
relative to a rectangular window, while broadening the main lobe. Δf is a grid
spacing, not a promise to resolve two nearby tones. Nyquist is fs/2; aliasing
cannot be undone by spectral estimation. Odd-length transforms do not include
an exact Nyquist bin. Band limits must lie within the returned frequency range.

Absolute band power is

```math
P_{[a,b]} = \int_a^b \widehat S(f)\,df.
```

Soma integrates with the trapezoidal rule and linearly interpolates density at
both endpoints. Mu is defined operationally here as [8,13] Hz and beta as [13,30]
Hz; these are configurable via `band_power`, and physiology does not imply fixed
boundaries for every participant. Shared endpoints have measure zero. Band
integration is an approximation on the estimated grid, particularly for narrow
bands and spectra concentrated at endpoints.

Exact discrete Parseval uses `sum(PSD)*Δf` for density bins. Trapezoidal integration
halves the DC and Nyquist endpoint weights and therefore need not equal that
sum for broadband signals. The exact test uses a single rectangular, detrended
segment and a bin sum. Pure-tone tests avoid endpoint power. Overlapping Hann
estimates weight samples and remove segment means, so full-record mean square
is only approximately equal to integrated Welch PSD for noise and nonstationary
signals.

PSD is V²/Hz. Its square root is amplitude spectral density, V/√Hz. A band
integral is power, V². Taking the square root of band power gives an RMS voltage;
none of these is the sinusoid's peak amplitude without the corresponding model.

Numerical test tolerances:

- Bin-centered 10/20 Hz peaks: within one frequency bin (default 0.5 Hz).
- Integer-cycle tones: integrated PSD and mean square within relative 1e−10;
  this accommodates floating-point trig and FFT roundoff, not estimator bias.
- Exact rectangular Parseval: relative 1e−12.
- SciPy mean Welch equivalence: relative 1e−12, absolute 1e−30 V²/Hz for near-zero bins.
- Seeded noise, amplitude modulation and burst: relative 10% power tolerance on
  60 seconds. It covers finite-sample weighting, per-window detrending and
  nonstationarity; it is a regression tolerance, not a confidence interval.

References: [NeuroDSP Welch API](https://neurodsp-tools.github.io/neurodsp/generated/neurodsp.spectral.compute_spectrum_welch.html),
[Welch (1967)](https://doi.org/10.1109/TAU.1967.1161901), and
[SciPy spectrogram](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html).
