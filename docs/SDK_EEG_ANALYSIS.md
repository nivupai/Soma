# EEG analysis conventions

Signal values use volts for EEG, sampling rate uses Hz and time uses seconds.
`eeg_spectrum` rejects other units; convert µV by 1e-6 explicitly. Existing `welch`
continues to support general signal units without changing its meaning. Metadata
and events retain recording identity; the cached EEGBCI reader never downloads.
Close the returned Raw or use the metadata convenience function that closes it.

Welch returns one-sided density in V²/Hz with explicit segment length, overlap,
window, averaging and constant detrend. The SDK uses the original NeuroDSP
implementation and disables hidden fast-length adjustment. Integrating density
with interpolated band endpoints gives absolute V² band power. A bin peak is not
an unbiased oscillator frequency estimate. Median averaging retains its existing
no-bias-correction convention. Segment clipping, invalid bands and nonfinite data
are rejected. `Spectrum.metadata` reports resolution and segment count.

Trial PSD axes are trial×channel×frequency. Morlet axes are
trial×channel×frequency×time with valid full-wavelet-support masks. Morlet V² power
is not a V²/Hz PSD; frequency averaging is not spectral integration. Epoch
acceptance and artifact exclusions must remain explicit. No SDK helper silently
reconstructs rejected trials, reference baselines or missing event meanings.

`calibrated_detector` takes already filtered voltage values, low/high amplitude
thresholds and minimum seconds. It reuses NeuroDSP dual thresholds and compensates
for its median normalization. Filtering, boundary guards, a permitted calibration
interval and observed exposure are caller responsibilities. Intervals are half-open
sample indices [start, stop). Bursts are threshold/scale-dependent descriptions,
not direct measurements of discrete biological states. The example sine is wholly
synthetic; it does not establish population, clinical or anatomical validity.

Execute `python -m examples.eeg_analysis`; expected peak=10 Hz and mu power=8e-12 V².
