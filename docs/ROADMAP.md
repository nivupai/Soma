# Roadmap

Milestones 1–3 now provide explicit EEGBCI ingestion, array contracts, NeuroDSP
spectra, continuous preprocessing, template geometry, duration-aware trials,
rest-reference modeling, Morlet power, ERD/ERS, failure-aware cohorts,
one-factor-at-a-time robustness analysis, continuous bursts, subject-level
statistics, synthetic laboratories and profiling.

Milestone 4 is not started. A future separately requested milestone could focus
on larger prespecified replication cohorts, manually reviewed artifact examples,
small-sample uncertainty calibration, and improved censoring/missingness models.
The five-subject percentile bootstrap undercovers in the recorded normal
simulation, so stronger population claims need an explicitly justified design
and uncertainty method. Burst definitions need sensitivity and SNR validation;
they are operational threshold events, not identified neural mechanisms.

Optional ICA would require reviewed assumptions and provenance. Classical
motor-imagery decoding would require leakage-safe subject/run evaluation.
Neither is implemented. Source localization still requires measured electrode
positions, anatomical coregistration, reference-aware forward models,
conductivity assumptions, inverse regularization and simulation checks.
Structural MRI/fMRI/registration require their own validated affine, coordinate,
statistical and interpolation contracts. Template sensor metadata is not a
substitute for these. No MRI, source model, deep learning or dashboard was added.
