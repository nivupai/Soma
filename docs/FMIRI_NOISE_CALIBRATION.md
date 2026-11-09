# Temporal-noise calibration

M13's finite-sample feasible AR(1) findings motivated a prespecified comparison
of OLS, feasible AR(1), supported Nilearn AR(2) and a small known-covariance GLS
reference. AR(2) support uses the installed Nilearn0.14.1 implementation and its
seeded coefficient clustering; no production voxel solver is reimplemented.

Original development streams14142 onwards were used by tests and a two-replicate
smoke run. The separately sealed validation amendment assigns15142–15241 for the
final100 realizations per scenario, before accessing those streams. Conditions,
models, q thresholds and contrasts remain unchanged. Each realization is shared
across estimators for paired methodological comparison, not independent model
replicates. The same seed indexes/innovations also pair scenario perturbations;
700 scenario rows are not700 independent trials. No model is selected by its activation extent or reliability score.

Independent synthetic HRF convolution is inherited from M13. Innovations are
independently seeded Gaussian noise, filtered after500 burn-in samples to form
stationary AR(0.6) or AR2(0.5,0.2). Scenarios: Gaussian null, AR1 null/alternative,
AR2 null,2s HRF delay, omitted nuisance and3mm smoothing. Primary effects are
beta3 in known positive/negative regions. Smoothing also transforms expected
spatial betas, so signal spread is not automatically misclassified as false
positives; HRF/nuisance misspecification remains a deliberate stress condition.

The small GLS oracle validates finite symmetric positive-definite covariance,
rank, contrast dimensions and positive residual DOF. Cholesky whitening and QR
solve beta, residual scale and c'beta variance. Independent tests use dense
covariance-weighted normal equations, a stationary AR1 Toeplitz formula, AR2
Yule-Walker recurrences and rho0 OLS limiting behavior. This reference is restricted
to small matrices/a prespecified voxel; known covariance is unavailable in human
inference and cannot be substituted as an empirically calibrated production model.

Report beta bias, empirical beta SD, estimated SE,95% Student-t coverage, uncorrected
voxel p<.05 rates/power, null-family any-BH rejection, alternative false-discovery
fractions and true-positive fractions, native/whitened residual lag, condition,
DOF and failures. Null any-rejection equals FDR only in the global-null setting.
Voxel probabilities differ from family error, and BH depends on valid probabilities
and suitable dependence assumptions. Native residuals are Y-Xbeta using the
unwhitened design; whitening follows the fitted temporal model. Small whitened
lag-one correlation is not proof that all temporal dependence is removed.

Wilson95% Monte Carlo intervals use seeded realizations as Bernoulli units for
coverage/power/any-rejection. Voxels are never counted as independent simulation
trials. Ratios/mean voxel fractions are descriptive unless another uncertainty
interval is explicitly supplied.100 realizations have limited tail precision;
retain excess false positives and poor coverage, not just favorable noise models.
The synthetic correctness tests use broad stochastic bounds and independent
arithmetic, not exact noisy coefficient recovery or hardware-speed cutoffs.
