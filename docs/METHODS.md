# Milestone 2 scientific methods

This pipeline characterizes event-based sensor-level mu/beta power, not source
activity, behavioral accuracy, or population effects. The initial recording is
PhysioNet EEGBCI S001R04, 64 EEG channels at 160 Hz. Run 4 means unilateral hand
imagery; runs 8 and 12 share this task. All stages retain subject, run, recording
and annotation identity. The motor-imagery workflow rejects other run types;
the general event decoder still supports their different meanings.

## Referencing, DC and channels

`select_eeg` requires unique available EEG channels and rejects selected channels
already marked bad in MNE metadata. The real default uses all 64 EEG channels
for an instantaneous arithmetic average reference: y_c(t)=x_c(t)−mean_c x_c(t).
This changes the signal and spatial covariance. QC flags alone do not remove
channels, interpolate them, or establish a clean reference. A contaminated
channel can influence an average; the channel report must be inspected. Numerical
functions accept an explicit channel subset for alternative reference sets.
`reference='none'` preserves the acquisition reference. Units remain volts.

Global mean subtraction is an explicit optional stage (`remove_dc=False` by
default); the default high-pass handles DC and slow drift without a redundant
mean-removal step. The Welch estimator still subtracts each segment's constant
mean, inherited from Milestone 1. No ICA or automatic artifact correction runs.
Raw data and annotations are never changed by preprocessing.

## Continuous filtering and transients

The default SciPy Butterworth band-pass has prototype order 4 and nominal
single-pass half-power cutoffs 1 and 40 Hz. Band-pass transformation gives order
8; forward-backward SOS filtering squares the amplitude response and gives an
effective order 16. Thus nominal cutoff gain is 0.5 (−6.02 dB amplitude) after
two passes, not −3 dB. The measured effective −3 dB crossings at 160 Hz are about
1.104 and 37.305 Hz on the saved response grid. Mu/beta lie within these bounds.
This IIR design has smooth transitions rather than independently specified FIR
transition widths. `preprocessing.json` saves SOS coefficients, response
frequencies, effective amplitude gain, phase, group delay and crossings at
−3/−6/−20/−40 dB; the response grid spacing is fs/(2×8192).

`phase='zero'` uses `sosfiltfilt`, odd reflection and an explicitly calculated
padding length. It is noncausal: later samples influence earlier output.
`phase='causal'` instead uses a single SOS pass, zero initial state, nonlinear
phase and frequency-dependent group delay. No cue-delay compensation is invented
for causal mode; its interpretation differs from zero-phase results.

A single-pass impulse response is probed for 120 seconds. The edge guard starts
where its remaining absolute tail is below 10^−4 of the total absolute response;
the probe must settle within its first 60 seconds. The guard is at least
3(2×number_of_sections+1) samples. Default guard/padding is 582 samples,
3.6375 seconds at 160 Hz. Trials overlapping either recording-boundary guard are
rejected and logged. Recordings too short for both guards raise an error. This
is a conservative operational guard, not proof that all transients are absent:
sharp events, abrupt artifacts and internal condition changes can ring or smear
across boundaries. Samples 1–3 s after a cue reduce onset contamination; they
do not remove this limitation. Filtering runs once over the continuous recording,
never independently on short analysis epochs.

Notch filtering is disabled. A requested IIR notch needs a nonempty explanation
of observed contamination, valid frequency and positive Q. Optional QC measures
line-band mean density ±1 Hz against 2–4 Hz flanks on the unfiltered and final
signals; it is not an automatic spectral significance detector. A notch above
an already attenuated low-pass region is usually unnecessary. The pipeline does
not decide to notch from a presumed country's mains frequency.

## Electrode geometry

Channel names are standardized with MNE EEGBCI naming, then matched exactly to
MNE's 1005 template. MNE 1.13 calls this `colin27_1005`; earlier supported MNE
versions call it `standard_1005`, so the installed API determines the name saved
in `geometry.json`. Every selected EEG channel must match, C3/Cz/C4 must exist,
and every position must be finite and nonzero. Positions are stored in MNE head
coordinates, meters. The XY sensor figure is an orthographic projection of 3D
positions, not a cortical map.

These are template coordinates, not measured subject digitization or an MRI
coregistration. `assign_geometry` also accepts a supplied MNE DigMontage with
explicit provenance, allowing future replacement without changing array APIs.
A caller supplying geometry is responsible for its measurement provenance;
finite-coordinate checks do not establish anatomical accuracy.

## Events, duration and sample coordinates

`Event` retains subject, run, original T code, semantic label, original annotation
onset, recording-relative onset, duration, sample, annotation index, source and
recording identity. Sample extraction uses MNE events with rounding and subtracts
`raw.first_samp`; relative seconds subtract `raw.first_time`. This also supports
Raw objects whose first sample is nonzero. Original annotation seconds remain
available separately. The parser validates labels, positive finite durations,
chronology, no overlaps, recording containment and onset/sample agreement within
half a sample. Gaps between annotations are permitted; they are not invented rest.
Variable positive durations are allowed and retained rather than forced equal.

## Epochs and QC

Default analysis windows are [1,3) seconds relative to cue. Offsets are rounded
to sample indices; endpoint exclusion is explicit, giving 320 samples at 160 Hz.
A window must be entirely in its event annotation and must not overlap another
condition. A caller can disable the own-annotation containment rule, but
incompatible annotations, recording boundaries and filter guards still apply.
Longer [0,4) windows are extracted separately for time-frequency context, with
the same checks. Longer windows can have different rejection counts, which are
reported separately. No trial is silently dropped.

QC reports peak-to-peak, RMS, variance, finite-sample count and excursions, all
in SI units. Defaults: recording-channel peak-to-peak 500 µV; trial peak-to-peak
300 µV; absolute excursion 150 µV; flat-channel SD below 0.05 µV. These configurable
operational thresholds are not a validated artifact classifier or optimal
subject-specific thresholds. Channel metrics report flags; trials exceeding a
criterion in selected analysis channels are rejected. The trial log includes
per-channel reasons, QC measurements, and exact sample ranges. Nonfinite raw
samples stop preprocessing before filtering; isolated nonfinite epoch inputs
are rejected rather than interpolated or omitted. Broad raw common-reference
excursions can trigger many pre-reference channel flags without implying that
every channel is defective.

## Welch PSD and absolute power

Trial PSDs still call genuine NeuroDSP Welch. Motor-imagery defaults use one-second
Hann segments, 50% overlap, mean averaging, no padding and constant segment
mean removal. A two-second trial provides three periodograms at 1 Hz spacing.
This differs explicitly from the two-second segments of the Milestone 1 whole-
record experiment. PSD shape is trial×channel×frequency, units V²/Hz. Mu [8,13]
and beta [13,30] powers integrate PSD with interpolated endpoints and the
trapezoidal rule, units V². Condition summaries preserve run and report trial
counts, arithmetic means and sample SDs; SD with one trial is unavailable.
They are descriptive, not confidence intervals.

## Three reference strategies

1. `none`: retain absolute power; normalized outputs are unavailable.
2. `condition_rest` (default): within each run, average power over separately
   extracted, accepted T0 [1,3) windows. Each reference annotation and sampled
   interval must meet `minimum_rest_s=2`. This pools rest across the run, including
   potentially post-imagery recovery. It is not a trial-matched causal baseline.
3. `matched_rest`: propose [−3,−1) seconds before each imagery cue. The whole
   interval must be in one actual T0 annotation, satisfy minimum duration,
   recording/filter guards and QC. The reference log retains its rest event
   index and imagery trial identity. Missing or rejected references leave that
   trial's normalized values unavailable; absolute powers remain.

Welch band power is compared only with Welch band power computed using the same
estimator, channels and bands. Morlet power is compared only with Morlet power
at identical frequencies/channels. Condition-rest Morlet reference is its valid
[1,3) samples averaged over time then over accepted rest context trials. Matched
Morlet reference uses only full-support time points in its accepted rest interval.
References are never borrowed between runs. Sparse/insufficient rest cannot be
replaced by an assumed pre-cue interval.

## Morlet resolution and edge handling

MNE `tfr_array_morlet` uses 8–30 Hz centers every 1 Hz, five cycles, zero mean,
FFT convolution, no decimation, and one worker. Arrays are trial×channel×frequency×time;
time is relative to cue in seconds. No xarray dependency is needed for these
fixed named coordinates.

For frequency f, Gaussian envelope sigma_t=n_cycles/(2πf). The actual MNE
wavelet is truncated approximately at ±5 sigma_t. Sigma_f=f/n_cycles. Power
FWHM in time is 2√ln(2) sigma_t, and in frequency is 2√ln(2) sigma_f: at 10 Hz,
about 0.133 s and 3.33 Hz. Frequency centers 1 Hz apart are highly correlated;
160 samples/s do not imply independent millisecond-scale dynamics.

Soma builds the actual installed MNE wavelets, rejects a segment shorter than
any wavelet, and masks every time point whose discrete wavelet support would
cross either epoch edge. MNE's convolution uses finite-array boundary handling
internally; unsupported estimates are never reported as supported observations.
At 160 Hz, support half-widths are about 0.494 s at 8 Hz and 0.131 s at 30 Hz.
The frequency×time support mask and half-widths are saved. This masks numerical
convolution edges, not all physiological temporal smearing or continuous-filter
transients. The recording guard is applied independently before epoching.

MNE wavelet power has voltage-squared scaling under its wavelet normalization;
it is not a calibrated PSD density or equal to sinusoid mean-square power.
Band trajectories average wavelet powers at centers within inclusive band limits
(13 Hz contributes to both adjacent descriptive trajectories). They are not
frequency-integrated Welch powers. Figures of wavelet ERD average frequency-wise
percent changes and need not equal normalization of a band integral. Two
simultaneous tones may beat in instantaneous wavelet power; temporal averages
are appropriate for stationary analytical comparisons.

## ERD/ERS and lateralization

For aligned power P and reference R:

```math
ERD = 100(P-R)/R,\quad L=\ln(P/R),\quad D=P-R.
```

Negative percent means suppression; positive means enhancement. Natural log is
not dB. Reference <= the configured floor, nonfinite values and missing references
are masked with NaN, never repaired with epsilon. Default floors are 10^−20 V²
for band and wavelet powers (RMS scale 0.1 nV), explicitly configurable numerical
validity cutoffs, not physiological noise-floor estimates. Absolute differences
remain computable for finite inputs even if division is masked. Zero task power
has −100% change but unavailable finite log ratio. Coordinate/shape mismatches
and negative powers raise errors. NPZ retains explicit masks; CSV uses empty
cells for unavailable quantities and strict JSON uses null rather than NaN.

Exploratory lateralization is (P_C4−P_C3)/(P_C4+P_C3), dimensionless. Positive
means lower C3 absolute power; negative means lower C4 absolute power. This is
not a contralateral source estimate. Baseline asymmetries, reference, volume
conduction and artifact contamination can alter its sign. A subject need not
show an expected motor-imagery pattern.

## Synthetic ground truth and tolerances

The 68-second model alternates four-second rest with four-second left/right
imagery, four trials per hand and a final rest. Channels C3/Cz/C4 contain 10 µV
10 Hz and 6 µV 20 Hz tones plus seeded 0.5 µV Gaussian noise. Left imagery scales
amplitudes [0.8,0.7,0.5], right imagery [0.5,0.7,0.8]. Thus power factors are
squared and expected changes are [−36,−51,−75]% or [−75,−51,−36]%. Optional
1 mV pulses test rejection rather than artifact correction. The laboratory uses
`reference='none'`: average referencing three coherent model channels would
change this specified ground truth. Real EEG defaults remain average reference.

Noiseless unfiltered tests at 100/160/256 Hz require band normalization within
10^−8 percentage points, averaged wavelet normalization within 10^−6, and ideal
ratio formulas within floating-point tolerances. Noisy two-second Welch tests
allow 5 percentage points, accounting for only three overlapping periodograms
and beta tone SNR around 25 dB; this is an engineering tolerance, not a confidence
interval. Gaussian noise realizations and finite reference estimates affect
individual trial ratios. A steady-tone filter test independently checks the
measured sinusoid amplitude against |H|² within 10^−5 relative error and tests
negligible zero-phase quadrature. Original Milestone 1 assertions are unchanged.

## Authoritative references

- [PhysioNet dataset and task semantics](https://physionet.org/content/eegmmidb/1.0.0/)
- [MNE EEGBCI loader](https://mne.tools/stable/generated/mne.datasets.eegbci.load_data.html)
- [MNE standard montages](https://mne.tools/stable/generated/mne.channels.make_standard_montage.html)
- [MNE annotation/event conversion](https://mne.tools/stable/generated/mne.events_from_annotations.html)
- [MNE Morlet array API](https://mne.tools/stable/generated/mne.time_frequency.tfr_array_morlet.html)
- [SciPy Butterworth design](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html)
- [SciPy SOS forward-backward filtering](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html)
- [NeuroDSP Welch API](https://neurodsp-tools.github.io/neurodsp/generated/neurodsp.spectral.compute_spectrum_welch.html)

# Milestone 3: replication, bursts and robustness

The prespecified design, cohort rules, statistical units, outcome definitions,
missingness policy and interpretation boundaries are in [PROTOCOL.md](PROTOCOL.md).
Milestone 1 and 2 estimators and defaults remain available without changed APIs.

## Continuous burst implementation

The installed NeuroDSP 2.3.0 signatures and source were inspected before wrapping:
`filter_signal(..., filter_type='fir', n_cycles=7, return_filter=True)`,
`amp_by_time(..., f_range=None, remove_edges=False)`, and
`detect_bursts_dual_threshold(..., f_range=None, min_n_cycles=None,
min_burst_duration=3/f_low, magnitude_type='amplitude', avg_type='median')`.
Soma filters a reflected continuous signal once, measures its amplitude, computes
rest/fixed physical thresholds, then calls the genuine detector. The detector's
own Hilbert computation is retained rather than duplicating its hysteresis or
minimum-duration implementation. Low/high thresholds are divided by its input
median amplitude so internal normalization cancels exactly. No samples are
silently omitted before this normalization.

The valid observation mask excludes the original broad-band filter guard plus
half the actual FIR kernel plus two seconds of extra Hilbert guard at each end.
FIR coefficients, threshold calibration, rest exposure and edge lengths are saved
per subject/run/channel/band/strategy. Detection is not repeated on two-second
trial snippets. Accepted event windows map the continuous detections into
half-open observations. Every fragment retains absolute and cue-relative times,
original event/trial identity, duration, amplitude and censoring flags.

`burst_dynamics.csv` contains per-trial 100 ms event-relative bins and their
actual exposure/burst seconds. This is binned occupancy over accepted analysis
windows, not a full unobserved pre-cue trajectory. Overlap/smoothing of Hilbert
and FIR estimates prevents independent-time-point inference. Both primary
strategies use accepted same-run rest; unavailable calibration gives unavailable
metrics, not a zero-burst assertion. A fixed-voltage mode supports synthetic
benchmarks only when explicitly selected.

## Controlled numerical interventions

The pulse-train laboratory holds a 10 Hz carrier and known bouts at 5–7, 12–14
and 20–22 s within a 30 s record. Interventions reduce burst amplitude to 0.6,
shorten durations to one second, keep only one bout, or increase broadband noise
without altering true bouts. With a low constant oscillatory floor, mean-square
ratios approach 0.36, 0.5 and 1/3 for the first three interventions. Burst count
and occupied time need not respond to amplitude in the same way as band power.
Changing noise or thresholds can change detected boundaries despite identical
underlying oscillatory intervals.

Abrupt real sinusoid gating violates ideal analytic-envelope separation; Hilbert
ringing means exact sample-wise threshold boundaries are not ground truth.
Direct detector timing is tested within one 10 Hz period (0.1 s) per edge;
occupancy tolerance follows 2 edges×0.1 s×number_of_bouts / total duration. FIR
integration tests allow one lower-band period per edge for envelope broadening.
Noiseless interior amplitude/power scaling remains a tight analytical benchmark.
Detector invariance is checked for count/overlap, not an invented promise of
identical threshold samples under amplitude rescaling.

The cohort simulation uses individual lognormal baseline scale, an individual
contralateral amplitude factor, shared run/channel amplitude variability,
trial-specific variability, independent run noise, known high-envelope intervals,
optional omitted annotations and pulses. Seeds derive from global seed, subject
and run via SeedSequence, preserving individual parameters across runs while
changing run noise. Ground truth is explicitly **before referencing/filtering**.
No-reference numerical comparisons validate C3 paired log-power recovery; an
average-reference simulation is not falsely asserted to preserve the same truth.

## Statistics and uncertainty

The hierarchical module implements transparent subject-vector percentile
resampling in bounded memory chunks. It pairs within run before run aggregation,
prevents duplicate subject/outcome rows at the resampling boundary, and retains
missing subject counts. Natural-log absolute-power contrasts are dimensionless
log ratios. Within-run normalized log-power contrasts can change when references
or valid trial sets differ; shared condition-rest denominators cancel only under
the relevant equal-reference/trial assumptions.

Burst means also receive subject-level contrast CIs; raw occupancy/rate summaries
are exposure-weighted within run before equal-run subject aggregation. Complete
burst duration/amplitude contrasts can be missing when no complete bursts exist;
zero occupancy is not filled with zero mean duration. Lateralization reports
arithmetic and logarithmic sensor contrasts separately. Subject exclusion
estimates and run SDs describe robustness, not population exclusion decisions.

The uncertainty laboratory runs independent normal-subject simulations and saves
every interval plus aggregate coverage and its exact binomial interval. This
exposes substantial percentile undercoverage at five subjects; the nominal 95%
forest plot intervals are exploratory, not validated confidence guarantees.
Optional exact sign flips and Holm correction are described in PROTOCOL.md;
there is no trial-level randomization or time-frequency cluster inference.

Additional authoritative API references:

- [NeuroDSP dual thresholds](https://neurodsp-tools.github.io/neurodsp/generated/neurodsp.burst.detect_bursts_dual_threshold.html)
- [NeuroDSP amplitude](https://neurodsp-tools.github.io/neurodsp/generated/neurodsp.timefrequency.amp_by_time.html)
- [NeuroDSP filtering](https://neurodsp-tools.github.io/neurodsp/generated/neurodsp.filt.filter_signal.html)
- [SciPy bootstrap interval terminology](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)

Soma's subject resampling is its own small NumPy implementation; citing SciPy's
interval documentation does not imply that SciPy performs the cohort grouping.


## Milestone 4

The immutable `REPLICATION_PROTOCOL.md` and sealed configuration define the
primary analysis. Subjects 6–35 are disjoint from the initial five; all requested
runs and failures appear in QC. Equal-subject log-power contrasts use at least
two paired runs. The ten inherited one-factor settings are all retained, including
unchanged primary log-power results under changes affecting only normalization
or burst definitions. This is not ten independent replications.

Reference auditing filters acquisition-referenced voltages once, then applies
linear reference transforms. The same channel filters commute with these linear
transforms. Compare both reference-specific accepted trials and the identical
intersection across all three reference choices. The retained-set difference
minus the common-trial transform difference is an accounting remainder, not a
causal decomposition of artifact mechanisms. Trial-deletion changes are exact
within-condition contributions to the run contrast. Largest peak-to-peak excerpts
are visual review candidates, without automated physiological artifact diagnosis.

The inference and simulation assumptions, failure rules and target definitions
are specified in `STATISTICS.md`. Nominal 95% intervals are pointwise; the two
primary sign-flip tests alone receive Holm correction. Secondary intervals and
sensitivity analyses are exploratory. No mixed-effects, classification, ICA,
source reconstruction or MRI model is introduced.


## Milestone 5 decoding

The sealed `DECODING_PROTOCOL.md` precedes model experiments. Development subjects
1–35 and prospective subjects 36–65 are separated at the data-loader and command
boundaries. Use a fixed nine-channel sensor set after continuous validated
preprocessing and a common QC/context-retained trial set. Nine prespecified models
cover motor mu/beta spectra, multichannel powers, NeuroDSP bursts, MNE CSP,
regularized covariance, Euclidean/Riemannian MDM and tangent logistic regression.
All learned transforms stay inside fresh training pipelines. Split memberships,
inner candidates and fit states make leakage checks inspectable.

See `DECODING_METHODS.md` for estimands, source/target separation, fixed adaptation,
null procedures and failure semantics. Source patterns remain sensor transforms
with template locations. Decoding performance neither proves anatomical origin
nor establishes clinical utility, causal motor representation or online BCI
performance. These retrospective zero-phase epochs are not a causal online system.


## Milestone 6 source methods

The sealed SOURCE_MODELING_PROTOCOL.md fixes subject 1 runs 4/8/12, ico3 fsaverage
white sources, a three-shell BEM, fsaverage_1005 template sensors, average EEG
reference, signed normals, depth 0.8, λ²=1/9, and rest-background shrinkage 0.1.
Existing EDF, event, filtering, QC and [1,3)-s epoch APIs are reused unchanged.
MNE minimum norm and dSPM are applied trial by trial. NeuroDSP vertex powers
precede condition/run and template-ROI averaging. The evoked comparison holds
nave=1 fixed to isolate averaging from inverse changes. No source-map population
inference or anatomical truth claim is made. See SOURCE_MODELING_METHODS.md for
units, covariance dependence, inverse assumptions, synthetic controls and the
participant-MRI adapter boundary; SOURCE_MODELING_VALIDATION.md records outcomes.
