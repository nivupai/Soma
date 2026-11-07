# Milestone 5 decoding results — v0.5.0

The initial decoding protocol was sealed before model experiments. Subjects 1–35
are exploratory development data. Subjects 36–65 were accessed only after the
separate committed freeze; all three prospective modes are now complete. All
nine models are reported without held-out winner selection.

Initial canonical protocol SHA-256:
`11912588d1457a334580eab3fa1093367a762ee94c0157ed6d71cdaa849547bf`.

## Completed prospective evaluation

The separately frozen configuration was committed as **a6b458f** before access.
Its canonical SHA-256 is
`7eced826d6024e633400917fb9dc1c2db26898b85b9ef6b6da47e67603f5d439`.
Freeze time: `2026-11-07T05:29:04.732664+00:00`; first access:
`2026-11-07T05:30:13.518648+00:00`; completion:
`2026-11-07T05:34:22.409338+00:00` (all UTC). The implementation is feature
commit **3816e4e**. All three prospective manifests identify the clean freeze
commit and unchanged numerical source digest `8b737ed92e21614a9b013671`.

All 90/90 held-out recordings completed. All 30 subjects contributed all runs;
1,234/1,350 proposals survived common analysis/context QC (91.41%). Every test
run retained both classes. No resampling, model selection, preprocessing change,
hyperparameter search or feature selection used these outcomes. This is a
prospectively reserved partition of an existing public dataset, not prospective
clinical data collection or an externally registered clinical trial.

| Frozen model | Zero-shot N=30, mean BA [95% t interval] | Within-held-out N=30, mean BA |
|---|---|---:|
| motor_mu_lr | 56.18% [52.33, 60.03] | 51.77% |
| motor_bands_lda | 58.65% [54.80, 62.50] | 53.89% |
| multiband_lr | 60.77% [56.53, 65.02] | 56.11% |
| burst_lr | 57.62% [53.80, 61.44] | 54.06% |
| csp_lda | 54.00% [51.13, 56.87] | 57.04% |
| covariance_lda | 56.72% [53.28, 60.16] | 54.97% |
| euclidean_mdm | 50.83% [49.61, 52.04] | 52.60% |
| riemann_mdm | 50.87% [49.58, 52.16] | 54.52% |
| tangent_lr | 56.58% [52.75, 60.41] | 55.17% |
| dummy | 50.00% [degenerate interval] | 50.00% |

Zero-shot training contains only subjects 1–35; every target participant remains
outside fitting. Within-held-out training uses two runs from that same target
subject and the third for testing, with fixed parameters. Those are different
training budgets and estimands, not interchangeable measures of generalization.
Intervals above are pointwise nominal subject t intervals. All nine models are
reported in the original order; no winner was selected after held-out access.

The three prespecified prospective paired tests were:

| Contrast | Mean difference | 95% subject t interval | Sign-flip p | Holm p |
|---|---:|---|---:|---:|
| tangent_lr − multiband_lr | -4.193 pp | [-8.112, -0.274] pp | 0.03635 | 0.07270 |
| riemann_mdm − euclidean_mdm | +0.048 pp | [-1.471, +1.566] pp | 0.95930 | 0.95930 |
| csp_lda − multiband_lr | -6.776 pp | [-10.513, -3.040] pp | 0.00085 | 0.00255 |

Under the declared symmetric-null assumptions, CSP is lower than multiband power
in this frozen broadband configuration after Holm correction. The tangent
contrast's unadjusted t interval excludes zero, but its Holm p=0.07270 does not
pass 0.05. The Riemannian-versus-Euclidean MDM advantage observed in development
is absent prospectively. This does not establish that CSP or manifold methods
are intrinsically inferior; preprocessing and domain shifts constrain this result.
Sign-flip p-values use 19,999 seeded draws and are Monte Carlo approximations.

Zero-shot equal-subject/run metric summaries illustrate why accuracy alone is
insufficient (right is positive):

| Model | Accuracy | Sensitivity | Specificity | ROC-AUC | Brier | Log loss |
|---|---:|---:|---:|---:|---:|---:|
| multiband_lr | 60.86% | 49.89% | 71.65% | 0.6679 | 0.2371 | 0.6707 |
| tangent_lr | 56.43% | 45.91% | 67.25% | 0.6213 | 0.2541 | 0.7203 |
| dummy | 49.79% | 100.00% | 0.00% | 0.5000 | 0.2500 | 0.6932 |

Tangent probabilities have worse proper scores than the prior dummy despite
above-chance balanced accuracy. Reliability plots are descriptive; no probability
calibration was tuned on held-out data. MDM distance margins supply AUC but no
claimed calibrated probabilities. Full per-run/subject metrics and confusion
counts are retained alongside these summaries.

Prospective labeled adaptation uses the same 819 evaluation trials from runs
8/12 at every calibration count. All 30 participants support every count:

| Model | k=0 | k=4 | k=8 |
|---|---:|---:|---:|
| multiband_lr | 62.92% | 62.80% | 63.16% |
| tangent_lr | 58.63% | 59.14% | 58.92% |

The k=8 versus k=0 mean changes are +0.24 pp for multiband and +0.30 pp for
tangent; these small descriptive changes do not establish meaningful adaptation
benefit. Pooling eight target examples among 1,441 source trials gives the target
only about 0.55% of training mass. This is a fixed baseline, not an optimized
adaptation rule. It must not be tuned further using the same reserved cohort.

The prospective audit passed 11 direct checks over saved memberships, labels,
fits and inputs. All 195 source-plus-target EDF checksums remain unchanged.
Zero-shot has exactly nine final fits and no inner selection; adaptation has
180 fits with source counts [718,723] plus balanced run-4 counts; within-subject
has 810 fits. All 999 pipeline fits and all mode statuses completed without
failure. Audit inputs and reproduction code are at `reports/m5-heldout/audit.json`
and `audit_reproduction.py`.

Prospective stage wall/CPU times were 22.21/21.99 s zero-shot, 21.40/21.28 s
adaptation and 26.09/25.89 s within subject. Process high-water RSS reached
1,259.73 MiB. The shared source/target bank is 531.01 MiB; within-target work
releases that bank and builds its own 244.96 MiB representation. Access-start to
completion elapsed 248.89 s, including downloads, data processing and rendering.
Pipeline inference still repeats some fold-local transforms for predictions,
margins and probabilities; the implementation prioritizes explicit training
boundaries over optimal latency. No online performance claim is made.

All prospective figures were inspected: model distributions/intervals, CSP
sensor patterns, covariance conditioning, tangent slices, confusion, reliability,
subject forests and adaptation. `figure_captions.md` records exact subject Ns,
trial-count meaning and uncertainty. Numerical validity does not imply transfer:
affine-invariant geometry handles one common invertible transform, not a different
unknown mixing matrix for every participant. Isotropic shrinkage adds another
limit to blanket invariance claims. Training pools retained trials; evaluation
and inner selection weight subjects equally, a distinct weighting interpretation.

## Development cohort and comparison

All 105 requested recordings completed. Nine-channel analysis/context QC retained
1,441/1,575 proposals (91.49%): 718 left and 723 right trials. Every run retained
both classes (at least two trials per class). All 35 subjects contributed all
three runs. No records, subjects or channels were silently replaced or resampled.
Primary metric is equal-subject balanced accuracy, averaging each subject's
observed run scores. Right-hand imagery is the positive class.

| Model | Within subject, N=35 | Cross subject, N=35 |
|---|---|---|
| motor_mu_lr | 59.00% [54.52, 63.49] | 58.88% [54.54, 63.22] |
| motor_bands_lda | 59.99% [55.58, 64.39] | 60.48% [55.72, 65.24] |
| multiband_lr | 62.03% [57.75, 66.31] | 58.61% [53.95, 63.27] |
| burst_lr | 58.75% [54.83, 62.67] | 56.44% [52.96, 59.93] |
| csp_lda | 58.22% [53.52, 62.91] | 54.11% [51.79, 56.44] |
| covariance_lda | 57.16% [52.94, 61.37] | 55.55% [52.72, 58.37] |
| euclidean_mdm | 50.99% [47.53, 54.45] | 49.83% [48.63, 51.04] |
| riemann_mdm | 56.88% [52.96, 60.80] | 52.38% [50.13, 54.63] |
| tangent_lr | 58.79% [54.09, 63.49] | 56.05% [53.53, 58.56] |
| dummy | 50.00% [degenerate interval] | 50.00% [degenerate interval] |

Brackets are nominal 95% subject t intervals, pointwise and descriptive for
cross-validation with overlapping training sets. The deterministic dummy is
50%; its zero variance is explicitly reported rather than inventing uncertainty.
Within-subject: 105 run-held-out partitions and 945 pipeline fits. Cross-subject:
five participant-disjoint outer folds with three grouped inner folds, 285 fits.
No failed model/fold cells or undefined test-class metrics occurred. Accuracy,
class counts, confusion, sensitivity/specificity, ROC-AUC, Brier and log loss are
in `metrics_run.csv`; probabilities/reliability are omitted for MDM margins.

The primary cross-subject paired contrasts were tangent−multiband −2.562 pp
(95% t interval −6.523 to +1.398, Holm p=0.19635), Riemannian−Euclidean MDM
+2.546 pp (−0.197 to +5.290, Holm p=0.12900), and CSP−multiband −4.495 pp
(−8.195 to −0.796, Holm p=0.05925). None passes the three-comparison Holm
criterion at 0.05. Point estimates do not establish universal method superiority.
Full paired percentile intervals and subject-deletion influences are retained.

## Limited labeled adaptation

Source-only inner choices remain fixed. Calibration is balanced labeled run-4
trials; evaluation uses only runs 8/12. These baseline scores therefore differ
from the main three-run cross-subject mean.

| Model | k=0 | k=4 | k=8 | Subjects |
|---|---:|---:|---:|---:|
| multiband_lr | 59.58% | 60.01% | 60.11% | 35 |
| tangent_lr | 56.85% | 57.04% | 57.96% | 35 |

All calibration cells completed. Pooling a few target trials gives modest mean
changes, not an optimal adaptation claim. There are 270 fits (60 source-only
inner fits and 210 adaptation fits); every calibration/test membership is saved.
The exact same target evaluation trials are used across calibration counts.

## Nulls and synthetic validation

All 19 seeded within-subject/run label permutations repeated nested tuning for
multiband/tangent logistic models (1,330 pipeline fits). Mean null balanced
accuracies were 49.94% and 49.64%; ranges 47.77–51.64% and 48.02–51.08%.
Observed means exceeded all 19 permutations, yielding the minimum attainable
Monte Carlo p=0.05 for both. This coarse conditional null assumes exchangeability
within runs and is exploratory under temporal dependence.

Known oscillatory mixtures gave 94.18% balanced accuracy for motor-mu logistic
and 100% for the other eight models; the dummy was 50%. Independent-label null
results ranged 45.93–52.05% across the four evaluated decoders. These are seeded
synthetic validation datasets, not estimates of real-world BCI performance.
Analytical tests independently recover known covariance matrices/CSP directions,
check distance/mean diagonal cases, rank-deficient mixtures, SPD floors,
congruence/permutation/scale properties and deterministic grouping. A deliberately
confounded subject-signature fixture scores 100% under random trial splits and
50% under subject-disjoint evaluation, demonstrating the leakage risk.

## Supplemental preprocessing diagnostic

This separately sealed, post-hoc development-only diagnostic never changes the
primary/prospective configuration. Fixed four-component, 0.1-regularized CSP is
compared on the same 1,223 retained trials across all variants. Intersection QC
removes S22 run 4, producing 12 recorded failed within-subject cells across four
variants, not an automatic one-run training substitute. Within scores use N=34;
cross-subject scores use N=35. The diagnostic is not the nested primary analysis.

| Fixed CSP variant | Within N=34 | Cross N=35 |
|---|---:|---:|
| primary | 57.96% | 56.63% |
| reference_none | 56.84% | 56.65% |
| reference_fz_pz | 56.35% | 55.97% |
| filter_8_30 | 61.94% | 62.34% |

The 8–30 Hz diagnostic is compatible with broadband covariance carrying less
transferable signal; it does not establish a causal mechanism. The prespecified
1–40 Hz primary filter is retained for prospective evaluation. No configuration
is promoted after seeing these diagnostic outcomes. The exact executed script
is archived with its matching SHA-256; the repository script later shortens only
a figure caption to satisfy Ruff.

## Performance and artifacts

The complete final development suite took 470.79 s. Stage wall/CPU times were
31.37/31.04 s within subject, 259.36/255.38 s cross subject and 24.57/24.57 s
adaptation; null refits and feature/cache work account for the remainder.
Process high-water RSS reached 1,013.13 MiB by adaptation. Fit BLAS threads are
bounded to one on macOS 15.7 ARM64 with ten logical CPUs. The shared numerical
bank is 286.05 MiB, excluding aligned raw context and library allocations.
PSD extraction took 1.22 s, burst context 4.07 s, trial OAS 0.32 s.
These are local measurements with possible concurrent verification, not isolated
hardware guarantees. Per-fit wall/CPU timings and warnings are retained.

`reports/m5-development-final`, `reports/m5-synthetic-verified`,
`reports/m5-benchmark-verified`, and `reports/m5-decoding-sensitivity` hold figures
and machine-readable data. Inspected figures include model/subject summaries,
CSP template sensor patterns, eigenvalue conditioning, tangent-coordinate slices,
confusion matrices, reliability, adaptation curves and synthetic recovery/distances.
Figure sample sizes and uncertainty are specified in their associated tables and
captions; trial-level reliability/confusion counts are descriptive correlated data.

## Measured synthetic computational stages

These are actual instrumented stages on six-subject known-mixture data, not
extrapolations to the real cohort. Tracemalloc increases runtime; process RSS
is a cumulative high-water mark. All-data timing objects are discarded rather
than reused by the separately fresh nested pipelines. The representation-bank
stage includes PSD, burst context and per-trial OAS (substage times are saved).

| Stage | Wall seconds | CPU seconds | Peak traced MiB |
|---|---:|---:|---:|
| PSD_and_burst_context | 6.2409 | 6.0106 | 64.575 |
| OAS_covariances | 0.2729 | 0.2705 | 0.892 |
| MNE_CSP_fit | 0.0880 | 0.0870 | 28.932 |
| Riemannian_100_distances | 0.0234 | 0.0230 | 0.009 |
| training_tangent_fit | 0.0348 | 0.0348 | 0.912 |
| tangent_mapping | 0.0130 | 0.0129 | 0.905 |
| logistic_fit | 0.0067 | 0.0067 | 0.174 |
| nested_cross_subject | 11.3465 | 11.3403 | 30.852 |

Released-code synthetic/benchmark outputs are at `reports/m5-release-synthetic`
and `reports/m5-release-benchmark`; numerical validation results agree with the
preserved earlier runs.

## Prospective status and limitations

Prospective evaluation completed under the separately committed freeze, with
all nine models and unchanged rules. Development results remain exploratory.
The reserved cohort is now used; it cannot serve as an independent confirmatory
sample for future decisions chosen using these outcomes.
Retrospective zero-phase filtering is not an online BCI pipeline.
Automatic QC is not expert artifact diagnosis; template patterns do not locate
sources. Fixed subject IDs are not random population sampling. Shrinkage is not
generally affine-equivariant, CV errors share training data, and classifiers may
learn nuisance covariance or subject signatures. No deep network, MRI, source
localization or Milestone 6 work is included.
