# Frozen EEG transfer readiness

Unlike the unavailable historical M22 state, M24 now has authentic newly fitted
numeric state under its own training seal and immutable release identity. This
resolves model archival completeness, not scientific input comparability.

| Mode | Current status |
|---|---|
| Exact new-model transfer | NOT_COMPARABLE for audited external candidates: reference, sampling, timing or missing channels differ |
| Prespecified harmonization | BNCI001/Cho require a new sealed, physically justified contract and evidence review; not executed |
| Missing-channel interpolation | Unsupported; especially BNCI004 with only three EEG channels |
| External refitting | Separate future experiment, never unchanged-model transfer |
| External human inference | BLOCKED: no acquisition authorization, permission-cleared inputs or reviewed evidence bundle |

`soma benchmark external verify-transfer MANIFEST ID --candidate DATASET` checks
actual private release/capsule integrity before returning metadata compatibility.
It does not read target signals or run inference. A matching feature-vector shape
is insufficient. Physical channel identity, reference pool, unit conversions,
cue-relative windows, filter conventions and provenance must all be established.

The source contract retains the EEGBCI average over all EEG before ROI selection.
BNCI001's22-channel reference cannot be asserted to reproduce the source64-channel
operator.250→160Hz and trial-start3–5s versus cue-relative1–3s are declared technical
changes, not exact transfer. Cho's512Hz sampling and timing/reference conventions
require distribution-specific validation. No target-fitted scaler, tangent reference,
covariance population mean, label inversion or calibration is silently permitted.

Default model prediction requires the source implementation and environment identity.
The exact private dependency snapshot is a tested reproduction environment; ordinarily
resolved installations and other platforms are not automatically approved for these
human weights. CI covers fictional cases only. No human external accuracy, uncertainty,
p-value, spectral/covariance shift or physiological inference is available.
