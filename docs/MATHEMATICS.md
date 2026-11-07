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

## Event-based extensions

Milestone 2 adds average referencing, continuous Butterworth SOS filtering,
annotation-contained half-open epochs, Morlet wavelets, explicit rest references,
ERD/ERS and lateralization. Their equations, units, measured filter behavior,
reference assumptions, support masks and tolerance derivations are documented in
[METHODS.md](METHODS.md). Welch density normalization and band integration above
are unchanged; the motor-imagery experiment explicitly uses one-second segments
rather than Milestone 1's two-second whole-record defaults. MNE wavelet power
must never be used as a Welch density denominator or treated as calibrated PSD.

## Repeated-measures estimands

For subject s, paired run r, channel c, band b, let P denote integrated trial
Welch power (V²). The primary run contrast is

```math
u_{srcb} = \frac{1}{n_L}\sum_{i\in L}\ln P_{srcbi}
          -\frac{1}{n_R}\sum_{i\in R}\ln P_{srcbi},\qquad
\delta_{scb}=\frac{1}{R_s}\sum_{r\,\mathrm{paired}}u_{srcb}.
```

Both conditions must have valid observations in a run. The cohort estimate is
`mean_s(delta_s)` over available subjects, never over all trials pooled across
subjects. Its unit is natural log ratio; exp(delta) compares geometric mean
powers. Absolute contrasts use arithmetic mean differences in V²; ERD contrasts
are percentage points. Equal-run averaging defines an estimand different from
pooling runs with unequal retained trial counts.

Subject bootstrap samples S subject contrasts with replacement, averages them,
and takes empirical alpha/2 and 1−alpha/2 quantiles. This approximates uncertainty
under independent representative subjects. It is not a finite-sample guarantee;
the five-subject normal Monte Carlo coverage is explicitly reported. CIs are
pointwise, not simultaneous. Paired standardized d_z is mean(delta)/SD(delta),
undefined if subject SD is zero; it is not a source-level or causal effect size.

For an optional symmetric subject-null sign-flip test, the statistic is
`abs(mean(delta))` over sign patterns epsilon_s in {−1,+1}. Exact two-sided p is
the proportion of all patterns at least as extreme; Monte Carlo uses a plus-one
correction. Floating-point ties use tolerance proportional to the data scale,
not an absolute voltage-dependent constant. Holm adjusted p-values are the
monotone cumulative maxima of `(m−i+1)*p_(i)`, clipped at one. The tested family
is all power channel/band/outcome cells in that execution.

## Burst measurements and censoring

Let B[n] be a continuous dual-threshold detection mask, V[n] the supported-sample
mask, and W an accepted event window. With uniform fs:

```math
E=\frac{1}{f_s}\sum_{n\in W}V[n],\quad
T_B=\frac{1}{f_s}\sum_{n\in W}B[n]V[n],\quad
\mathrm{occupancy}=T_B/E,\quad \mathrm{rate}=N_{\mathrm{observed\ onsets}}/E.
```

Exposure E is seconds; rate is s⁻¹. E=0 means unavailable, not zero. Rates count
continuous onsets whose beginning is observed, not every entry of an ongoing
burst into a window. Mean burst amplitude averages Hilbert amplitude (V) over
observed burst samples. Complete durations average only intervals with both ends
observed. Censored intervals contribute occupancy and amplitude but are excluded
from complete-duration means, which can therefore be biased toward shorter bouts;
no survival model is claimed.

NeuroDSP normalizes Hilbert amplitude A by its whole-input median M. To apply
physical thresholds L/H volts, pass L/M and H/M. The resulting inequalities are
A>L and A>H. Rest-dual L/H are per-channel same-run accepted-rest median multiples;
rest-percentile uses empirical reference quantiles. A_min duration is three cycles
at the band's lower edge. A zero input returns no detections explicitly.

For a stationary sinusoid with amplitude factor a, power scales a². For disjoint
integer-cycle bouts at fixed amplitude, mean-square power scales approximately
with occupied fraction; changing burst count and changing duration can produce
similar band power. Hilbert/filter smearing, noise, thresholds and censoring
prevent identifying a unique underlying burst mechanism from band power alone.
Subject-level associations do not resolve causality.


## Reference and uncertainty identities

For an acquisition-referenced channel x and an explicit reference r,
Var(x−r)=Var(x)+Var(r)−2Cov(x,r), and the Welch spectral identity is
P(x−r)=P(x)+P(r)−2 Re S(x,r), using identical windows, detrending and scaling.
These identities explain reference-dependent power; they do not imply invariant
sensor power or recover absolute physical potentials. Covariance uses population
normalization consistently. Template coordinates remain templates.

For subject s, run r, calculate d_sr = mean(log P_left) − mean(log P_right).
The primary d_s is the unweighted mean of eligible paired-run d_sr, and the
population estimate is mean_s d_s. The standard error is sd(d_s)/sqrt(N).
A t interval uses t_(N−1,1−alpha/2). Bootstrap indices select whole subjects;
studentized pivots use (mean(d*)−mean(d))/[sd(d*)/sqrt(N)]. Invalid zero-SE
pivots count toward the declared failure fraction. Basic limits reflect percentile
limits about the observed estimate. SciPy computes BCa bias and acceleration.
No failed interval is silently replaced.

Simulation coverage is sum(contains declared target)/R, with procedure failures
counted as noncoverage. MCSE=sqrt(p(1−p)/R); exact binomial confidence limits
also appear in saved data and plots. Conditional-success coverage is separately
labeled. Coverage of the structural clean effect and of the observed-data target
are distinct in contamination, MNAR and preprocessing-shift scenarios.
