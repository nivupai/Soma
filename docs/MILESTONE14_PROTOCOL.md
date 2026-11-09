# Milestone14 frozen protocol: preprocessing audit and reliability

Baseline0312635, Soma0.13.0. Freeze before new evaluation BOLD/model outcomes.
SPM auditory is previously inspected educational development data, never a new
prospective validation set. M13 null findings informed this protocol. New seeded
simulations are prospectively specified software experiments, not human validation.
Reuse existing FunctionalRun, Nilearn fits, Volume/Frame/Transform, PyBIDS, ROI,
AnatomyReport, physical hashes and content-cache infrastructure. No new production
preprocessor or voxel GLM solver.

## Data and staged access

Primary ds000114v1.0.2 (CC0; cite Gorgolewski et al.2013). Metadata inventory first;
pilot subject01, sessions test/retest, task fingerfootlips, exact supplied Finger,
Foot,Lips names, no motor-imagery substitution. Download only those two raw motor
BOLD acquisitions and their T1w references, plus required events/acquisition metadata.
Verify annex content hashes, geometry/TR/counts and completeness without fitting
raw data. No cohort downloads unless an audited two-session pilot succeeds.
If suitable derivatives exist, evaluation subjects02–10 are untouched until the
pilot workflow is fixed; all10 only if actual assets/resources permit. Failures,
missing data and exclusions remain explicit. No validation-driven parameter choice.

Require explicit fMRIPrep GeneratedBy/version, linked raw sources, preprocessed
BOLD sidecar and space, matching masks/confound TSV+JSON, anatomical reference,
BOLD/T1 and template transforms as applicable, and available HTML QC evidence.
Read metadata and inspect existing local derivatives; filenames are not proof.
No silent container installation, template download or expensive external run.
An explicitly invoked local fMRIPrep adapter may execute a recorded command with
network/template policy left explicit; otherwise report preprocessing unavailable.
Raw BOLD is never analyzed as preprocessed in M14. SPM remains development only.

## Primary model and motion policy

Common T1w or explicitly identified template space across sessions, independently
validated transforms and ROI atlas provenance. No same-shape alignment inference.
Primary Finger versus baseline; secondary Foot,Lips and Finger-.5Foot-.5Lips.
SPM HRF, cosine drift1/128Hz, no separate image high-pass, AR(1), smoothing6mm,
explicit acquisition slice-time reference, no silent scaling. Comparable effects
require explicit intensity-scale identity. Contrast BH FDRq.05 across analysis-mask
voxels separately per contrast; unthresholded effects/variances remain available.
This is not FWE or population activation inference. ROI means are descriptive
unless spatial covariance is separately modeled.

Primary six measured rigid-motion columns. One-factor expanded12-motion;
motion+explicit available retained CompCor; and six-motion+FD>.5mm spikes plus
provided nonsteady-state indicators. No invented physiology/FD/DVARS. Missing
required columns/provenance makes the run ineligible, not an automatic fallback.
Only an undefined first FD can be assigned0 by declared policy. No volume deletion:
spikes preserve the original acquisition/event/noise time grid. Exclude runs with
mean FD>.5mm, >20% FD>.5mm, or design residual DOF<20; rank/conditioning failure
also excludes. Record all counts/ranks/reasons. Confounds never selected by extent.

One-factor sensitivity: OLS, supported Nilearn AR(2), temporal HRF derivative,
0 versus6mm smoothing, and the declared nuisance alternatives. No uncontrolled
Cartesian product or selection of the most favorable reliability. Raw motor runs
cannot fill missing derivative comparisons.

## Calibration and independent oracles

Seed14042 development, heldout independent seed streams14142 onwards. Primary
100 realizations for each of stationary Gaussian null, AR(.6) null, AR(.6) beta3,
AR2(.5,.2) null, and AR(.6) alternative with2s HRF delay. Each is fit by OLS,
feasible AR(1), supported AR(2); same realization across estimators. Optional
one-factor omitted nuisance and3mm smoothing under AR(.6) alternative,100 each.
Known covariance GLS is a restricted small-matrix reference at a prespecified
voxel, not a production image solver. Independently compare Cholesky whitening QR
with dense covariance-weighted normal equations, stationary covariance and rho0
limit. No reference comparison is two calls to Nilearn.

Report effect bias, empirical SD versus estimated SE,95% Student-t coverage,
voxel p<.05 false positives/power, family BH null-any-rejection and alternative
false-discovery fraction/power, native/whitened lag diagnostics, condition, DOF,
failures and seed rows. Bernoulli rates use Wilson95% Monte Carlo intervals;
replicate/subject units are explicit. Do not treat voxel counts as Monte Carlo
replicates. Retain AR1 miscalibration.100 realizations give limited tail precision.
No noise/threshold choices are tuned on favorable validation outcomes.

## Reliability, spatial/ROI and multimodal safeguards

Retest same participant/task/contrast, two different documented sessions, common
identified grid, comparable preprocessing/HRF/smoothing/intensity scale and ROI
ontology. Require successful provenance audits before human fits. Report contrast
correlation, sign-specific FDR Dice (empty/empty undefined), ROI signed/absolute/
symmetric-relative changes, mask coverage, extrema displacement in world mm,
within-session variance summaries and QC differences. Selected extrema are noisy
features, not anatomical ground truth. Registration error is not identified by
correlation or peak displacement alone.

Cohort summaries resample participants, never voxels. ICC(A,1), two-way random,
absolute agreement, single measurement, two sessions; at least5 complete subjects
for the software estimate, report model assumptions and subject bootstrap/delete-one
sensitivity. One subject never yields cohort ICC. Synthetic10-subject two-visit
cohort validates numerical paths, not human repeatability.

ROI labels require explicit native/template identity, atlas source/version,
hemisphere conventions, nearest-neighbor pull chain, coverage and partial-volume
warnings. Real motor/somatosensory ROI interpretation requires appropriate atlas
and registration evidence; no atlas is silently downloaded. SimpleITK can inspect
ITK affine/composite/displacement transforms and apply controlled LPS-mm landmarks;
nonlinear transforms retain their representation and explicit reference grids.
File from/to labels alone cannot prove point direction or invertibility. Numerical
landmark checks and overlays are separate from independent anatomical truth.

Cross-cohort EEG motor imagery versus motor execution is descriptive only,
conditional on actual compatible ROI results. No participant correlations across
unrelated cohorts. ds000117 remains an adapter pending visit/task/transform data;
no simultaneity or EEG-to-BOLD conversion. Missing real results remain unavailable.
All MRI, participant outputs and identifying hashes stay ignored. Commit only
code/config/docs and aggregate receipts; no push or Milestone15.
