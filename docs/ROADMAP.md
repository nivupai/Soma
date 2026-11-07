# Roadmap

Milestones 1–3 now provide explicit EEGBCI ingestion, array contracts, NeuroDSP
spectra, continuous preprocessing, template geometry, duration-aware trials,
rest-reference modeling, Morlet power, ERD/ERS, failure-aware cohorts,
one-factor-at-a-time robustness analysis, continuous bursts, subject-level
statistics, synthetic laboratories and profiling.

Milestone 4 adds a sealed 30-subject replication, explicit all-subject opt-in,
resumable per-record processing, covariance/cross-spectral reference auditing,
five subject-mean interval methods, influence and distinct weighting summaries,
and a completed seven-scenario calibration over N=5–100. Small-sample bootstrap
undercoverage and biased-target coverage remain explicit scientific findings.
See `MILESTONE4_RESULTS.md` for measured outcomes and limitations.

Milestone 5 now implements trial-level decoding, spectral/burst baselines, MNE
CSP, explicit covariance rank/SPD regularization, Euclidean/Riemannian MDM,
training-reference tangent features, grouped nested evaluation, fixed limited
adaptation and auditable leakage checks. Development subjects are 1–35;
prospective subjects 36–65 require a separately frozen, verified configuration.
See `DECODING_METHODS.md` and `MILESTONE5_RESULTS.md` for the staged research record.

Milestone 6 has not started. A separate request could define independent-cohort
domain-shift validation, better justified adaptation or probability calibration.
The existing prospective cohort must not be reused to choose a winner and then
be presented as an independent confirmatory sample again.

Optional ICA would require reviewed assumptions and provenance. Classical
motor-imagery decoding would require leakage-safe subject/run evaluation.
Neither is implemented. Source localization still requires measured electrode
positions, anatomical coregistration, reference-aware forward models,
conductivity assumptions, inverse regularization and simulation checks.
Structural MRI/fMRI/registration require their own validated affine, coordinate,
statistical and interpolation contracts. Template sensor metadata is not a
substitute for these. No MRI, source model, deep learning or dashboard was added.
