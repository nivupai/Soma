# fMRI numerical validation

The baseline was verified before changes:691 passing tests,62 warnings,74.44s.
No original tests or historical MRI/EEG reports are changed. New offline tests
use synthetic images only; real optional integrations do not fetch during pytest.

Simulation uses an independent 0.01s stimulus grid, causal FFT convolution and
normalized difference of Gamma(6) and Gamma(16)/6 densities. It does not call
Nilearn's HRF or design generator to create ground truth. It includes positive
and negative activation regions, known beta3, independent Gaussian errors, optional
AR(0.6), spatially filtered noise, motion-like nuisance, linear drift, differing
TR and delayed HRF. Smoothing the noise changes its variance; this is recorded
as a separate sensitivity condition, not a matched-noise SNR comparison.

An independent QR OLS oracle solves R beta=Q.T Y, residual sigma²=SSE/(n-p),
contrast effect=c.T beta and variance=sigma²*norm(solve(R.T,c))². It is restricted
to small full-rank analytical examples and is not a production voxel GLM.
Known noiseless coefficients and noisy fitted effects, variances and Student-t
p-values are checked independently. No exact noisy beta recovery is required.
Independent HRF quadrature is compared to Nilearn within discretization error
at TR1/2/3s; causal event onset and contrast signs/differences are tested.

Validation seeds13142–13161 are separate from development13042. Twenty null
replicates per setting report uncorrected rejection fractions and any BH rejection
under Gaussian/AR noise. These are finite Monte Carlo estimates; nominal q is not
an empirical guarantee. Strong OLS inflation under AR errors and residual feasible
AR(1) miscalibration are retained as limitations. Tests separately verify broad
Gaussian null behavior, FDR rejection being a subset of p<q and reduced whitened
lag correlation under AR(1), without machine-speed or exact random-score thresholds.

Adversarial tests cover bad timing/TR/units/headers, qform/sform disagreement,
confound count/nonfinite/missing columns, name collisions, event/subject identity,
rank/condition/DOF, missing contrast conditions, masks/grids, unsafe contrast names,
raw preprocessing boundaries, derivatives and content/config cache invalidation.
Spatial tests use independent linear functions in physical RAS metres, explicit
voxel-world calculations, nearest-neighbor ROI translations, projection coverage,
hemisphere validation, missing/wrong-direction transforms and multimodal mismatches.
All numerical/registration/source baseline tests remain operational in the full suite.

Measured final errors, null rates, test counts and timings are recorded in
[M13 results](MILESTONE13_RESULTS.md) and the aggregate verification receipt.
