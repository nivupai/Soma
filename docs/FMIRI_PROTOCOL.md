# Milestone 13 prospective task-fMRI protocol

Frozen before reading new BOLD outcomes, baseline73b9ed0 (Soma0.12).
Scope: a research first-level GLM engine using Nilearn, not fMRIPrep, a clinical
activation detector or a joint EEG/fMRI generative model. Reuse Soma Volume,
VoxelMap, Frame/Transform, explicit pull resampling, source hashing, private output
guards and provenance. FunctionalRun is a distinct 4D representation. Models are
serial with one job. No original data, individual maps or participant metadata in Git.

## Data and partitions

Development/validation numerical data are independent seeded synthetic streams
(seed13042, validation13142 onwards), with known spatial betas, explicit HRF,
Gaussian/AR/spatial noise, drift and motion-like nuisance. Validate noiseless
analytic OLS and noisy distributions; no outcome-based model selection.

Real demonstration: UCL SPM MoAEpilot BIDS archive, public education/evaluation
release at https://www.fil.ion.ucl.ac.uk/spm/download/data/MoAEpilot/MoAEpilot.bids.zip
via Nilearn0.14.1 fetch_spm_auditory. Pin actual archive/input hashes privately.
One subject, one auditory run, expected96 volumes/TR7s. Inspect actual JSON/events
before modeling. Listening versus implicit rest is primary; reject unexpected task
semantics rather than guess. Do not silently delete early volumes: four explicit
initial-volume spike nuisance regressors address initial transients, incompletely.

The provider calls these raw data, not validated preprocessed derivatives. The
normal fit API requires documented validated preprocessing, an aligned brain mask
and explicit processing-space identity. An explicit SPM educational raw-demo option
permits an exploratory fit with this limitation prominent in every report. No claim
of motion correction, distortion correction or spatial normalization. Motion and
physiology columns cannot be invented. Missing real motion measurements limit
interpretation. Raw-demo results do not fulfill validated-preprocessed human
activation evidence. This is an honest capability boundary, not a preprocessing tool.

Optional ds000114v1.0.2: selected subject01, documented test/retest sessions,
fingerfootlips task. Discover actual sessions, conditions and sources; require
compatible external preprocessed derivatives/confounds/masks and transformation
provenance. Do not download the full dataset or fit raw images as validated data.
If derivatives unavailable, report real retest unavailable; exercise API synthetically.
It is not a heldout validation cohort unless choices freeze before its outcomes.

Optional ds000117: inspect current OpenNeuro metadata/version and modality files,
face task, matching IDs within one release only. MRI and EEG/MEG visits are distinct;
EEG may be embedded in MEG FIF, not standalone EEG files. Prior versions renumber
subjects; never infer mappings. Require explicit visit/task/ROI/transform evidence
before matched comparison. Metadata inspection alone is not multimodal analysis.

## Fixed modeling policy

Scan times t=arange(n)*TR, slice_time_ref0. SPM canonical HRF; derivative is a
separate sensitivity setting. Cosine drift high-pass1/128Hz with intercept;
no additional image temporal filtering (avoid inconsistent filtering of X/Y).
Primary feasible AR(1) Nilearn FirstLevelModel, no signal scaling/standardization,
smoothing6mm for SPM only, no smoothing synthetic primary. Compare OLS and alternate
HRF/drift/nuisance settings separately; never select the best activation score.
Noise model, mask, smoothing, timing and design names are recorded.

Confounds must match retained scan count and exact run identity. Require selected
columns; reject missing/nonfinite values. Optional motion derivatives have first
sample0 by definition; optional FD spikes threshold0.5mm (FD first value may be
missing only by explicit policy). No volume deletion/time reindexing. Spikes are
one-hot regressors, with count, remaining degrees of freedom and rank recorded.
Default reject rank deficiency, near-zero regressors, nonpositive residual degrees
of freedom and condition number>1e10. Contrasts bind actual names or explicit
finite vectors; no zero substitution for missing conditions. Fixed effects combine
only same-subject, same-task, same-space grids and estimands, not population inference.

Primary auditory condition beta>0 remains signed with two-sided t/p inference.
Retain effect, variance, t,z and descriptive unthresholded maps. BH FDRq0.05 over
all in-mask voxels per contrast; no arbitrary cluster threshold/FWE claim. Record
tails, DOF and family. No circular peak-selected ROI. Primary real ROI is whole
EPI intensity foreground; no atlas/hemisphere claim from scanner coordinates.
Imported anatomical ROIs require matched space, subject and source/atlas metadata,
explicit RAS-metre transform chain and nearest-neighbor label resampling.

## Reliability and multimodal limits

Retest same subject/task/contrast and validated alignment: map correlation,
thresholded Dice (empty/empty undefined), ROI effects/differences, voxel differences
and two-session sample variance. Two visits do not establish ICC/population
reliability, separate registration error or identify true physiological change.
Smoothing/noise/HRF/nuisance sensitivity are separate simulations, not tuning.

Cross-dataset ROI comparison is descriptive, independently normalized regional
patterns with explicit different subjects/tasks/modalities, no participant match.
Matched mode requires same participant within release, explicit visit mapping,
shared ROI ontology, spatial transforms and task provenance; never assumes
simultaneity. BOLD vascular/hemodynamic effects and EEG current/power are different
quantities; source leakage, registration and physiological variability remain
unidentified unless separately measured. No real comparison when required data
or transforms are missing. Synthetic interpolation/projection oracles validate
software only, not anatomical certification.

Protocol and configs are sealed by configs/fmri-freeze.json before real analysis.
Any amendment is separate; historical reports remain untouched. No M14 or push.
