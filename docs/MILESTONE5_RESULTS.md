# Milestone 5 decoding results — v0.5.0

The initial decoding protocol was sealed before model experiments. Subjects 1–35
are exploratory development data; 36–65 remain reserved pending the separately
committed final configuration and explicit prospective command. The table below
is development-only and does not select a held-out winner.

Initial canonical protocol SHA-256:
`11912588d1457a334580eab3fa1093367a762ee94c0157ed6d71cdaa849547bf`.

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

## Prospective status and limitations

Prospective evaluation is pending the separately committed freeze at this code
checkpoint. All model-selection rules remain fixed and all nine models will be
reported. Development data have already been inspected; their results remain
exploratory. Retrospective zero-phase filtering is not an online BCI pipeline.
Automatic QC is not expert artifact diagnosis; template patterns do not locate
sources. Fixed subject IDs are not random population sampling. Shrinkage is not
generally affine-equivariant, CV errors share training data, and classifiers may
learn nuisance covariance or subject signatures. No deep network, MRI, source
localization or Milestone 6 work is included.
