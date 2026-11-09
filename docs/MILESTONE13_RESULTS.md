# Milestone 13 — task-fMRI and guarded spatial interfaces

Soma v0.13.0 extends verified baseline73b9ed0. Baseline:691 tests passed,62 warnings,
74.44s. Existing APIs, original test files and historical reports are preserved.
The scientific protocol/configuration hashes were sealed before real BOLD analysis.
A separate sealed input amendment records the actual84-volume SPM release before
fitting. No Milestone14 or remote push is included.

## Implementation and boundaries

FunctionalRun is a typed4D acquisition with explicit timing, geometry, identifiers,
mask/confounds, processing-space and provenance. PyBIDS discovers events through
strict compatible inheritance, rejects ambiguous run/space selection and requires
external preprocessing evidence for normal fits. Raw BIDS is never assumed
motion/distortion corrected. Nilearn0.14.1 APIs, including first_level_from_bids,
were inspected; explicit FirstLevelModel construction enforces Soma's contracts.

Design, production OLS/feasible AR(1), typed contrasts, BH FDR maps, diagnostics,
within-subject fixed effects with effect-scale/HRF comparability guards, ROI analysis, sparse surface/volume operations,
retest metrics and multimodal regional guards are implemented. The independent
small QR oracle does not replace Nilearn's voxel engine. No fMRIPrep equivalent,
nonlinear registration implementation, joint EEG/fMRI estimator or deep fusion.

Normal fits require validated external preprocessing evidence. The SPM example is
an explicit educational exception: raw data with incomplete preprocessing/motion
information. Therefore the validated-preprocessed human activation criterion is
**not fulfilled**. Statistical thresholding does not remove that limitation.

## Numerical validation

71 added offline cases pass. Final full suite:762 passed,80 warnings,75.58s;
offline:745 passed,17 deselected,78 warnings,52.61s. All47 baseline test files
and652 historical report files remain byte-identical. Coverage includes independent HRF quadrature/TR and
causal timing, noisy/noiseless effects, difference contrasts, QR variance and t
probabilities, null behavior, AR whitening, rank/collinearity, bad metadata/events/
confounds/subjects, mask and ROI geometry, physical units, transforms, sparse
projection, cache invalidation, schema validation and multimodal incompatibility.

Independent QR versus production OLS maximum error: effect4.84e-14, variance7.63e-17.
The deterministic primary positive-region mean effect is2.96595 (truth3), with
correct negative-region signs. Independent trilinear physical-space oracle maximum
error is0.0. Known HRF delay, TR, smoothing, nuisance and noise changes are saved
as separate sensitivity settings, not selected to maximize detection.

Twenty independent validation seeds per noise/model setting give:

| Synthetic null setting | Mean voxel fraction p<.05 | Fraction with any BH rejection |
| --- | ---: | ---: |
| Gaussian, OLS | 0.0500 | 0.05 |
| AR(0.6), OLS | 0.1819 | 1.00 |
| AR(0.6), feasible AR(1) | 0.0678 | 0.20 |

These are finite Monte Carlo results, not proof of calibrated FDR. Feasible AR(1)
improves the misspecified OLS result but retains excess false positives in this
laboratory. A20-run any-rejection estimate has substantial binomial uncertainty;
no correction/model was changed to hide the finding. Nominal BH control assumes
suitable dependence and valid voxelwise probabilities.

Synthetic two-visit effect-map correlation0.982293 and thresholded Dice0.972973
are software demonstrations only. ROI changes, voxel RMSE and two-session variance
are retained; two maps from one simulated subject do not estimate population ICC
or distinguish registration, estimation and physiological variability in humans.

Review identified that Nilearn's AR RegressionResults.predicted uses its whitened
design. Soma's native residual diagnostic explicitly computes original modeled
Y minus unwhitened X beta instead of using that accessor. Native and whitened
residuals are distinct, and a generative-AR regression check prevents recurrence.
Final reports were regenerated; statistical maps remain exactly identical to the
pre-review computation. All final main reports share the corrected source hash.

## SPM auditory educational demonstration

The UCL archive supplies one64³×84 run,3mm voxels,TR7s, seven42-second listening
blocks. JSON states12 volumes already discarded by the user. Supplied onsets are
preserved; no further deletion or timing shift. The sealed four-initial-spike
nuisance policy remains explicit. No motion parameters were available or invented.

Primary model: SPM HRF, cosine drift1/128Hz, four spikes, intercept, AR(1),6mm
smoothing, no signal scaling or standardization. Design84×15, rank15, residual
DOF69, condition number27.5344. Listening versus implicit rest has two-sided BH
FDRq.05 over61,335 intensity-foreground voxels:9,630 rejected (7,788 positive,
1,842 negative). Effects, variance,t,z,p,q and rejection images remain available
privately and unthresholded maps are retained. Whole-foreground mean effect1.12448
native BOLD units is descriptive, not percent signal change or an auditory ROI test.
ROI inferential standard error is unavailable without spatial covariance modeling.

Visual inspection shows positive lateral patterns on both sides of the displayed slice and negative areas in
native voxel slices, plus a declining mean BOLD signal. No MNI/hemisphere or
anatomically localized auditory-cortex claim is made without registration evidence.
The mean-image/mask overlay is same-grid QC, not a T1 registration validation.

| Exploratory SPM setting | FDR rejected voxels | Foreground mean effect |
| --- | ---: | ---: |
| Primary | 9630 | 1.12448 |
| OLS | 9176 | 1.13672 |
| No initial spikes | 9536 | 1.14837 |
| HRF temporal derivative | 10136 | 1.14169 |
| No smoothing | 2416 | 1.14536 |

These counts measure sensitivity, not anatomical accuracy or a model ranking.
Motion/physiological nuisance sensitivity cannot be measured without actual
regressors. Native residual mean lag1 is-0.03543; whitened lag1 is-0.00579.
Whole-run drift and raw preprocessing limitations remain despite small lag values.

## Optional human reliability and multimodal status

Metadata-only remote inspection: ds000114v1.0.2 contains10 participants, documented
test/retest sessions and finger/foot/lips conditions. The selected participant has
10 raw BOLD files across tasks/visits. ds000117v1.1.0 contains16 participants;
selected inventory has nine BOLD and six MEG files across MRI/MEG visits, with no
standalone EEG files. EEG may be embedded in MEG FIF but channels were not read.
Provider numbering differs from older releases; no cross-release mapping is inferred.

Neither inspected tree exposes preprocessed BOLD/confounds tables. These inventories
do not prove preprocessing derivatives exist nowhere else. No bulk functional
images were downloaded for either dataset. Real ds000114 retest, registered
anatomical ROIs and participant-matched EEG/fMRI results are **unavailable**.
Adapters and safeguards are tested; simulated regional comparisons are explicitly
simulated and do not fulfill real multimodal analysis. Physiological equivalence,
simultaneity, leakage correction and registration-error decomposition are unclaimed.

## Derivatives, reproducibility and performance

Official offline bids-validator-deno3.0.2 with local BIDS1.11.2 schema passes the
supported analysis-mask datasets for real and synthetic fits. Statistical maps
lack a general standardized suffix in this schema and remain Soma custom reports;
no claim that all statistical files are standardized BIDS derivatives. Warnings
and full validator JSON are retained. Image entities, native affine, spatial
reference, source links, model/contrast/tail/units and provenance are preserved.
No unrelated artifacts are overwritten. No medical data are uploaded.

Completed-output reuse rehashes products under the same input arrays/geometry,
events, confounds, configuration, source and library identity. Changed/corrupt
outputs fail closed. It is whole-report verified reuse, not stage-level GLM
resumption. The contrasts CLI performs a genuine refit from recorded source specs;
its statistical maps are exactly equal to the primary fit. Design CLI also ran.

One job/OpenBLAS thread1. Final SPM analysis2.530s, peak whole-process
RSS907.016MiB; synthetic laboratory1.897s/
338.359MiB; supplemental spatial/performance/sensitivity
5.944s/1162.125MiB. These exclude interpreter
startup and input preparation where outside the timed report; RSS includes
libraries and is not incremental allocation.

Direct SPM component seconds: loading/materialization0.036883,
confounds0.000731, design0.003072,
design+GLM1.253151, contrast0.082717,
ROI0.001537, same-grid physical resampling0.012247.
Repeated fits benefit from OS caches; no cold-cache claim or machine-specific CI
thresholds. Full masked residuals require memory, but only one functional run is
processed at a time.

Final full/offline test results, hash counts and receipts are recorded in
[verification](VERIFICATION.md) and
[aggregate receipt](../experiments/milestone13/verification.json). Ruff lint,
formatting, strict mypy172 modules and dependency checks pass. Primary reports:
reports/milestone13-spm, reports/milestone13-synthetic and
reports/milestone13-supplemental. All figures have supporting numerical arrays;
medical images, individual manifests and input fingerprints remain ignored.
The final audit verifies97 output hashes and60 finite figure arrays, reviews nine
primary PNGs plus the separate ROI/null figure, and confirms identical statistical
maps on CLI refit. Completed-output hash verification/reuse took0.291s; this is
not a GLM refit benchmark.

The SPM provider permits personal education/evaluation; no broader license or
redistribution right is inferred. Tissue/conductor certification, clinical utility,
validated raw preprocessing, fresh prospective human generalization, real matched
multimodal inference and uncertainty decomposition remain unresolved. A proposed
Milestone14 would obtain/audit compatible preprocessing and transform evidence,
then prospectively validate multi-session inference/calibration. It is not started.
