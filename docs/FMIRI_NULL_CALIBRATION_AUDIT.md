# Milestone 14.1 null calibration audit

This addendum preserves Milestones 13/14 and their failed calibration evidence.
The exact baseline rerun preceded implementation. No threshold or generator was
selected to obtain 5% rejection. Aggregate numerical tables are in
`experiments/milestone141/verification.json`; full synthetic realizations, exact
designs/covariances, plot arrays and manifests remain under ignored
`reports/milestone141-*`. The protocol and final policy have separate hash seals.

## Historical reconstruction

At baseline `8e24b6e`, the original Milestone 14 experiment reproduces any BH
rejection in **100/100 OLS, 23/100 AR1, 24/100 AR2** realizations. Wilson 95%
intervals are [96.30%,100%], [15.84%,32.15%], [16.69%,33.23%]. These are repeated
historical seeds, not independent new evidence. Seeds 15142–15241; n=100 time
points, m=343 fixed-mask voxels, X has task/motion/trend/intercept, rank4 and
nominal residual df96; task contrast [1,0,0,0], two-sided q=.05 BH (SciPy).

The mean is 100 + .3 motion + 2 trend, with task coefficient exactly zero.
Gaussian innovation SD=.5, independent across voxels, temporal AR coefficient .6,
500 discarded startup samples. True separable error covariance is
`.25 * C_AR(.6) ⊗ I_343`, where C is stationary unit-innovation covariance.
The mean is in the nuisance span: this is a true global null for the contrast.
Float32 image storage introduces negligible rounding, not an omitted task signal.
`reconstructed-design-covariance.npz` saves all 100 realized X matrices, c and
true covariance. Reconstruction files were added after the reproduction manifest;
`reconstruction-receipt.json` hashes them separately. Milestone 13's earlier AR
startup differs (nonstationary initial state); it must not be conflated with
Milestone 14's burn-in generator. Both implementations were inspected.

Production obtains signed z from a t contrast, then `2*normal.sf(abs(z))`.
The new direct Student-t check differs by at most 4.45e-16, eliminating an observed
tail-conversion error as an explanation. Hand-calculated BH/BY/Bonferroni examples
and permutation tests agree. Effect, variance and p outputs from the bounded
matrix diagnostics agree with actual full image FirstLevelModel fits for all
three production estimators. No demonstrable scientific arithmetic bug was found.

## Independent staged experiment

Seed1411000 uses SeedSequence[seed,stage,condition,replication]. Different stages
and conditions are independent; estimators share a realization to permit paired
comparison. The 512 single-voxel and 128 spatial realizations per condition use a
fixed, full-rank design from seed1401000, n40/100/200, task beta0 under the null.
This is a controlled diagnostic family, distinct from the historical random-X
experiment. No replacement of the historical results is implied. Exact X/c,
temporal C, spatial G and `.25*G G.T`, mixture beta and variance-equivalent N are
saved. Stationary known GLS, independent estimated-stationary-AR1 GLS and known
parameter conditional AR startup are separate references. Estimated covariance
is not treated as known. Diagnostic matrices are capped at n200/m1000; the human
engine remains Nilearn FirstLevelModel.

At n100, selected **single-voxel** rejection/coverage estimates (512 realizations):

| True errors | Estimator | p<.05 | 95% interval coverage | Mean SE / empirical SD |
|---|---|---:|---:|---:|
| iid | OLS | 4.88% | 95.12% | 1.014 |
| iid | AR1 | 5.86% | 94.14% | .977 |
| iid | AR2 | 6.84% | 93.16% | .951 |
| AR(.6) | OLS | 17.58% | 82.42% | .690 |
| AR(.6) | AR1 | 6.64% | 93.36% | .953 |
| AR(.6) | AR2 | 6.25% | 93.75% | .951 |
| AR(.6) | known stationary GLS | 4.30% | 95.70% | 1.014 |
| AR(.6) | estimated stationary AR1 GLS | 6.64% | 93.36% | approximately .958 |
| AR(.6) | known conditional AR | 4.69% | 95.31% | approximately 1.012 |

Wilson intervals, QQ quantiles, KS distances and DKW bands are in the receipt;
KS p-values are diagnostic and do not certify calibration. For iid OLS the
marginal Wilson interval is [3.33%,7.11%]. Estimation-induced extreme tails can
be consequential even when a one-voxel 5% test looks close to nominal.

With n40/AR(.6), mean estimated AR1 coefficient is .389, single-voxel rejection
13.67% and coverage86.33%; known GLS rejects5.27%, coverage94.73%. At n100 the
estimated coefficient is .533 (unbinned OLS residual estimate .539) versus true
.6; at n200 .564. AR2 coefficients at n100 under true AR1 average [.555,-.032].
At n200 AR1 rejection remains7.03%, coverage92.97%; known GLS rejects6.45%,
coverage93.55%, subject to 512-sample uncertainty. Under true AR2(.5,.2), OLS
rejects16.99%, correctly specified feasible AR2 6.84%, known GLS5.47%; feasible
AR1 is conservative at3.91%. Misspecification can change the direction of error.

Global null with m343 independent voxels, n100, **128 independent families**:

| True errors | Estimator | Any BH rejection | Wilson 95% interval |
|---|---|---:|---|
| iid | OLS / known GLS | 5.47% | [2.67%,10.86%] |
| iid | AR1 | 15.63% | [10.35%,22.91%] |
| iid | AR2 | 21.88% | [15.59%,29.80%] |
| AR(.6) | OLS | 99.22% | [95.71%,99.86%] |
| AR(.6) | AR1 | 16.41% | [10.99%,23.78%] |
| AR(.6) | AR2 | 17.19% | [11.63%,24.65%] |
| AR(.6) | known GLS | 2.34% | [0.80%,6.66%] |

Under global null FDR equals any-rejection probability. Under alternatives it
does not: AR(.6) mixture BH mean FDP is .29076 OLS, .07354 AR1, .07680 AR2,
.04395 known GLS. Independent-replicate bootstrap95 intervals (10,000 resamples,
seed1411999) and power are in the receipt; OLS [.28361,.29836], AR1
[.06730,.07998]. The mixture includes positive/negative effects on the first/last
10% of voxels; active voxels are excluded from null calibration calculations.

Voxel families27/343/1000 and correlated/smoothed fields were all retained.
For smoothed AR(.6), BH any-rejection rates are85.16%/13.28%/15.63%/6.25% for
OLS/AR1/AR2/known GLS. Mean largest false cluster sizes are7.297/.328/.344/.141
(6-connected grid clusters, no cluster-significance claim). Spatial dependence
changes errors/clustering but is unnecessary for failure: independent voxels
already fail. Full per-condition results and correction comparisons are saved.

BY controls arbitrary dependence only when marginal p-values are valid;
Bonferroni also needs valid marginal tests. Under independent AR(.6), BY gives
78.13%/5.47%/6.25%/.78%; Bonferroni96.09%/15.63%/15.63%/2.34%. Lower numbers
are not a validation of the underlying feasible-AR probabilities.

## Root cause classification and restrictions

| Candidate cause | Evidence / conclusion |
|---|---|
| Implementation arithmetic | QR/precision oracles, full image comparison, direct t/z and correction checks pass. No demonstrated bug to patch. |
| Contrast/design/global null | Correct nuisance mean and beta0; exact X saved, full rank. Rank-deficient inputs are explicitly rejected. |
| Temporal model misspecification | OLS under AR noise severely underestimates SE. AR1 under true AR2 may instead be conservative. |
| Covariance estimation | Residual AR estimates biased downward at short n; estimation from the same data and tail-conditioned estimates accompany undercoverage. Unbinned stationary feasible GLS also fails, implicating estimation beyond Nilearn binning alone. |
| Finite-sample approximation | Plug-in estimated covariance is not fixed known covariance. Nominal Student-t ignores covariance-estimation uncertainty; iid overfitted AR also fails families. |
| Startup treatment | Known conditional and stationary references are much better calibrated; startup differences alone do not explain feasible-AR failures. |
| Degrees of freedom | n-rank(X) is conditional nominal df, not a proof of exact feasible-GLS t law. Contrast-variance-equivalent N is saved but is not Student-t df. No arbitrary df subtraction used. |
| Spatial dependence | Affects clustering and family behavior; not necessary for the failure. |
| Remaining uncertainty | AR2 clustering, rare extreme tails and contributions of estimation/bias/startup are not completely causally decomposed. Monte Carlo tails remain imprecise. |

Default `InferencePolicy()` labels outputs descriptive/experimental and sets
`confirmatory_claim_allowed=False`. Unsupported explicit confirmatory requests
raise an error. Human runs and feasible AR models are restricted; effect/variance
maps and residual diagnostics remain available. Existing numerical BH outputs
remain nominal, with policy metadata added; they are not silently certified.

The only allowed explicit confirmatory contract is **synthetic iid Gaussian,
fixed full-rank X/mask, independent voxels, OLS, no smoothing, n100, m1/27/343,
two-sided t, BHq.05**, with task/motion/trend/intercept design and explicit
provenance declaration. Assumptions are declared, not inferred or verified from
data. Mathematical OLS assumptions and observed uncertainty support this limited
class; one Monte Carlo family is not universal certification. Known GLS is a
synthetic reference, not an available human default. The final policy is sealed
after calibration and before the attempted human pilot, which fitted zero models.

Implementation references: [Nilearn run_glm](https://nilearn.github.io/stable/modules/generated/nilearn.glm.first_level.run_glm.html)
for covariance-model fitting and [SciPy false_discovery_control](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html)
for BH/BY and their dependence assumptions. Numerical evidence above comes from
the installed versions recorded in the experiment manifests, not the current
web documentation version. Explicit alternative-policy outputs use `q_by` or
`p_bonferroni` and `fdr_reject` or `fwe_reject` respectively. Default BH names and
values are preserved. Consumers selecting an alternative must use its named map.
