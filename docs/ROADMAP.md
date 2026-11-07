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
subjects 36–65 have completed the separately frozen prospective evaluation.
See `DECODING_METHODS.md` and `MILESTONE5_RESULTS.md` for the staged research record.

Milestone 6 has not started. A separate request could define independent-cohort
domain-shift validation, better justified adaptation or probability calibration.
The existing prospective cohort must not be reused to choose a winner and then
be presented as an independent confirmatory sample again.

Optional ICA remains unimplemented and would require reviewed assumptions and
provenance. Classical decoding now has leakage-aware subject/run evaluation,
without claims of clinical or online reliability. Individualized source localization still requires measured electrodes and anatomical
coregistration. Template forward/inverse operators, conductivity assumptions,
regularization and simulation checks are now implemented in Milestone 6.
Structural MRI/fMRI/registration require their own validated affine, coordinate,
statistical and interpolation contracts. Template sensor metadata is not a
substitute for these. No participant MRI pipeline, deep learning or dashboard was added.


Milestone 6 is implemented: frame-safe geometry, opt-in fsaverage anatomy,
MNE EEG BEM forwards, rank-aware noise covariance/whitening, minimum norm/dSPM,
bounded resolution analysis, cortical simulations, trial-wise exploratory
motor-imagery power and headless figures. See SOURCE_MODELING_VALIDATION.md for
the successful workflows and unfavorable recovery/leakage results. Individual
MRI registration, segmentation, FreeSurfer reconstruction, FEM, measured sensor
coregistration and independent anatomical validation remain future work.
Milestone 7 now adds the structural MRI subsystem described below.


Milestone 7 implements lazy anatomical volumes, explicit NIfTI geometry, RAS/LPS
and voxel maps, resampling, SimpleITK rigid/affine registration, conservative
labels/masks, physical surface extraction, mesh/containment diagnostics and a
subject-aware interface to future MNE anatomy. The actual SPM foreground mesh
fails topology and remains ineligible for BEM use. The measured fsaverage EEG
source pipeline is preserved. See MRI_VALIDATION.md.

A proposed Milestone 8 would validate participant-matched sensor/MRI coregistration
and anatomical conductor boundaries using independent anatomical evidence and
established tools, before any individual EEG forward inference. It would require
its own reviewed scope and data. Milestone 8 has not been implemented or started.
