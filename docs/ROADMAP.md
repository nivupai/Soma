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

A proposed Milestone 5 would prespecify expanded replication and reviewed artifact
labels, quantify selection/missingness sensitivity, and independently validate
any interval-selection decision. It requires a separate user request and has not
started. No automatic download of the remaining subjects is scheduled.

Optional ICA would require reviewed assumptions and provenance. Classical
motor-imagery decoding would require leakage-safe subject/run evaluation.
Neither is implemented. Source localization still requires measured electrode
positions, anatomical coregistration, reference-aware forward models,
conductivity assumptions, inverse regularization and simulation checks.
Structural MRI/fMRI/registration require their own validated affine, coordinate,
statistical and interpolation contracts. Template sensor metadata is not a
substitute for these. No MRI, source model, deep learning or dashboard was added.
