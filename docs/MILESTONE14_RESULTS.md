# Milestone14 results — implemented software, incomplete human acceptance

Soma0.14.0 extends baseline0312635. Baseline verification:762 tests passed,
80 warnings,79.28s. The protocol/configuration was sealed before new evaluation;
a separately sealed amendment assigns fresh validation seeds15142–15241 after
unit/smoke development used14142 onwards. Models, contrasts and thresholds were
not selected by favorable calibration or reliability. Historical reports remain
unchanged. **Complete acceptance is false: required human preprocessing/retest
assets are unavailable.**

## Real dataset coverage and provenance

Metadata inspection confirms ds000114v1.0.2, CC0,10 participants, test/retest visits
and actual Finger/Foot/Lips events. Only the selected pilot participant's two motor
BOLD runs and two T1w references were fetched:65,429,728 bytes total. Each object
matches its annex size/digest and an independently recorded SHA256. No other
participant images were fetched and no participant table was downloaded.

Both raw BOLD runs are64×64×30×184, TR2.5s, approximately4mm voxels. T1w arrays
are256×156×256, approximately1×1.3×1mm. Source event timing/weights and native
geometry were inspected and preserved. This older BIDS1.0.0rc2 layout is indexed
without claiming current-schema compliance. Original raw files are immutable. The earlier SPM auditory case was re-inspected
as a known raw educational development boundary; it is not a new confirmatory
fit or a substitute for audited motor data.

No compatible preprocessed BOLD, masks, confound TSV/JSON, transform chains or
reviewed fMRIPrep QC were found locally; the inspected public tree also exposes
no compatible preprocessed BOLD/confounds. This does not prove derivatives exist
nowhere else. fMRIPrep/ANTs executables are absent; Docker is installed but its
daemon is unavailable. No container/tool/template installation or expensive
preprocessing job was launched.

Actual audit:2 raw runs and2 T1w references inspected,0 eligible derivative sessions.
Pilot:1 participant requested,0 modeled/completed. Cohort:10 requested,0 attempted,
0 completed because the pilot gate failed. Real sensitivity:0 fitted settings.
All four commands return explicit unavailable/nonzero results, not fabricated
success. No raw motor BOLD was fit as fully preprocessed. Real motor effects,
FD/DVARS distributions, anatomical motor ROI reliability, cohort ICC and EEG/fMRI
regional comparisons are unavailable.

## Implemented audit and modeling safeguards

PreprocessingBundle/PyBIDS associate exact identities, raw sources, fMRIPrep
GeneratedBy/version, mask, T1w, confounds/definitions, space, transforms and HTML QC.
Checks cover qform/sform, units/TR/counts, finite BOLD, row alignment, source dataset
links, explicit slice-time reference, mask grid, T1 source identity and numerical
transform evidence. PASS means declared metadata/numerical/review criteria only;
independent anatomical validity remains INDETERMINATE.

ITK affine/composite/nonlinear transforms retain their actual representations.
Controlled RAS-metre/LPS-mm landmarks validate direction/reference grids and a
noncommuting rotation+displacement composition. Inversion is queried, not assumed;
no nonlinear deformation is converted into an affine. General nonlinear ROI
resampling is not implemented. Existing ROI/space/interpolation safeguards remain.

Minimal6-motion, expanded12-motion, retained metadata-defined CompCor and measured
FD>.5mm/nonsteady-state spikes are supported. Spikes retain the acquisition grid;
rank, conditioning and DOF are checked. Missing columns/definitions are not invented.
Prespecified exclusions are mean FD>.5mm,>20% high-motion frames or residual DOF<20.
Cohort expansion requires an intact current-source pilot and unchanged input/output
hashes, plus explicit per-participant configurations; it never downloads a cohort.

## Independent numerical validation and calibration

53 added cases pass. Independent Cholesky/QR GLS versus dense covariance-weighted
normal equations: maximum beta error2.22e-16, contrast-variance error6.94e-18.
Tests cover covariance/rank/DOF, stationary AR recurrences/rho0, AR2 estimation,
noise streams, source/session/TR/confound failures, transform direction/units,
nonlinear composites, masks, stale audits, ICC arithmetic/units, ROI geometry,
sign-sensitive retest and unavailable-data CLI behavior.

Final calibration:7 scenarios×100 realizations×3 production estimators =2,100
image fits, plus400 small known-covariance reference fits; **0 estimation failures**.
Seed indexes/innovations pair scenarios and estimators, so these are100 independent
seeds per scenario, not700 independent trials across all scenarios. Every replicate,
condition, design/noise setting and failure list is retained privately.

| Global null | Model | Prespecified voxel p<.05 | 95% CI coverage | Any BH rejection |
| --- | --- | ---: | ---: | ---: |
| Gaussian | OLS | .02 | .98 | .01 |
| Gaussian | AR1 | .04 | .96 | .15 |
| Gaussian | AR2 | .04 | .96 | .23 |
| AR(.6) | OLS | .15 | .85 | 1.00 |
| AR(.6) | AR1 | .04 | .96 | .23 |
| AR(.6) | AR2 | .04 | .96 | .24 |
| AR2(.5,.2) | OLS | .11 | .89 | .97 |
| AR2(.5,.2) | AR1 | .02 | .98 | .14 |
| AR2(.5,.2) | AR2 | .02 | .98 | .14 |

Rates are not interchangeable: the selected voxel can look well calibrated while
the family has excess tail rejections. Under AR(.6), BH-any Wilson95% intervals
are .963–1.000 (OLS), .158–.322 (AR1) and .167–.332 (AR2), all above nominalq=.05.
The feasible noise models do **not** establish valid FDR control, even under the
Gaussian global null. No threshold/model was changed to hide unfavorable results.
Known-covariance reference coverage is .98/.98/.99 for Gaussian/AR1/AR2 nulls,
with broad Monte Carlo intervals; it evaluates one voxel and supplies no empirical
family-error guarantee or human known-covariance model.

Under AR(.6) beta3 alternatives, mean bias is .0274/.0229/.0236 and estimated-SE/
empirical-SD ratios .776/1.074/1.119 for OLS/AR1/AR2. Prespecified-voxel power is1.0
in all three (a ceiling, not evidence they are equivalent). HRF delay produces
bias−.389/−.665/−.549 and coverage .75/.49/.80. Omitted-nuisance and smoothing
results remain separate stress/sensitivity experiments. Smoothing changes expected
spatial betas; signal spread is not counted automatically as null error. Wilson
intervals for coverage, voxel rejection/power and family any-rejection are in the
aggregate receipt; mean FDP/true-positive fractions remain descriptive;
100 realizations have limited tail precision. No universal calibration or clinical
inference claim follows from passing numerical arithmetic tests.

## Synthetic reliability and confound findings

A10-subject, two-visit analytic ROI experiment gives ICC(A,1)=.94960, subject-
bootstrap95% interval .84795–.97649. Delete-one ICC ranges .91311–.95686.
Mean paired ROI change .17782 (subject-bootstrap interval .14223–.21413) reflects
a known simulated session shift plus noise. These are synthetic observations,
not ds000114 effects or population clinical reliability. Subjects, never voxels,
are the resampling units. Negative ICC is not clamped and one subject cannot
produce a cohort ICC.

Synthetic fMRIPrep-shaped import sensitivity retained93/94/95/91 BH voxels for
minimal/expanded/CompCor/FD-spike strategies, with89/83/88/88 residual DOF.
These fixtures did not undergo actual fMRIPrep and are not anatomy/accuracy
benchmarks; larger counts are not better methods. Motion plots, design/correlation,
identity BOLD/T1 overlay, native/whitened residual ACF, session maps, ROI trajectories
and calibration curves are explicitly labeled simulated. The absent real-motion
and anatomical-registration figures cannot be replaced with these as human evidence.

## Reproducibility, performance and acceptance

Final full pytest:815 passed,87 warnings,78.11s. Offline:798 passed,17 deselected,
85 warnings,54.83s. All50 original test files and709 historical report files are
byte-identical. Ruff lint/format, strict mypy180 source modules and dependency
checks pass. Existing EEG/MRI/fMRI integrations remain operational in the full suite.

Final calibration took55.197s and321.33MiB whole-process peak RSS;
the synthetic import/cohort laboratory took1.561s and
388.98MiB. One job/OpenBLAS/OMP/ITK thread1,
no machine-specific thresholds. Timings include in-process reporting/plots but
exclude startup and downloads. Memory includes libraries, not incremental allocation.
Human GLM/preprocessing performance is unmeasured because those jobs did not run.

Audit verified52 output hashes,26 finite pickle-free figure arrays and five
reviewed PNGs. One post-review correction stored synthetic subject labels as
Unicode rather than object arrays; regenerated numerical results were exactly
unchanged. All final production source fingerprints agree. Input/content/config/
transform identities and private manifests preserve provenance without putting
medical data or identifying fingerprints in Git. Imported metadata checks and
legacy indexing are not a new full BIDS-compliance certificate; statistical maps
remain custom reports and inherited official BIDS schema tests pass.

Private roots:reports/milestone14-audit, pilot, cohort, sensitivity, laboratory,
and calibration. Public aggregate receipt:
experiments/milestone14/verification.json. No push or Milestone15.

Acceptance gaps: audited human preprocessing, a real two-session motor pilot,
bounded human cohort/ICC, independently aligned motor/somatosensory ROIs, and
real cross-cohort EEG/fMRI findings. A proposed next milestone should obtain/audit
those external derivatives and transforms, then execute the frozen pilot before
cohort expansion and further inference claims. It has not begun.
