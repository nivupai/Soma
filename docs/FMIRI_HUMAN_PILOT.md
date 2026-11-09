# Milestone 14.1 human motor test–retest pilot

**Unavailable: zero completed participants, zero eligible sessions, zero raw or
preprocessed models fitted.** The existing audit inspected the two raw sessions
and T1w references but could not find compatible audited fMRIPrep derivatives.
Both sessions are INDETERMINATE, not passed. No human contrast maps, registration
QC, ROI correspondence, test–retest correlations, uncertainty maps or HTML
preprocessing reports exist to inspect. No cohort ICC was calculated.

The final inference-policy checksum was frozen before the attempted pilot.
Existing `configs/retest-pilot.yaml` prespecifies Finger/Foot/Lips and FingerOthers
motor-execution contrasts, minimal confounds, AR1 and6mm smoothing. Such human
feasible-AR models are descriptive under the new policy; raw input is not a
substitute for preprocessing. Events were inventoried, but constructing new
session models and interpreting contrasts remains gated on preprocessing QC.
Motor execution is not interchangeable with motor imagery.

When validated derivatives become available, use the existing preprocessing audit
for subject/session identity, coordinate frames, BOLD/T1 geometry, TR/volume
counts, mask overlap, confound rows/motion, transform direction/composition,
source checksums, external version and report provenance. Inspect actual fMRIPrep
HTML reports and anatomical overlays; reject inconsistent derivatives. Then apply
the frozen event/confound/contrast strategy to corresponding spaces and ROIs,
preserve effects/uncertainty and descriptive two-visit comparisons with hashes.
Do not report inferential significance or single-person cohort reliability.

The current negative receipt is under ignored
`reports/milestone141-human-pilot`; aggregate status is committed in
`experiments/milestone141/verification.json`. All source MRI, participant-level
paths/hashes, derivatives and individual results remain excluded by `.gitignore`.
No preprocessing or human validity criterion has been declared satisfied by
synthetic tests.
