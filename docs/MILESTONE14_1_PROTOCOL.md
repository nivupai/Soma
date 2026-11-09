# Milestone14.1: null calibration and audited pilot protocol

Baseline8e24b6e, Soma0.14.0/815 tests. Exact original AR(.6) null reproduction
completed before implementation:100%/23%/24% any-BH rejection for OLS/AR1/AR2,
100 seeds15142–15241. These are historical repetitions, not new validation.
Preserve all prior reports/tests. No Explorer, large cohort, push or Milestone15.

## Staged statistical investigation

Separate incorrect arithmetic, wrong design/null, conditional/feasible covariance,
finite-sample approximation, startup treatment, residual-AR estimation, temporal
misspecification, spatial dependence and family correction. Do not change a null
or choose thresholds just to obtain5%. Retain all failures and negative results.

New independent random streams use SeedSequence with seed1411000 and stage/case/
replicate keys. Different conditions/stages are independent; estimators/corrections
share the same realization within a comparison. Small smoke checks use1401000.
Single-voxel stage:512 realizations each of Gaussian/AR(.6)/AR2(.5,.2),n100;
AR(.6) also n40/200. Fixed task/nuisance/intercept design, true task beta0.
Compare production Nilearn matrix OLS/AR1/AR2, known stationary-covariance GLS,
and estimated-AR1 stationary GLS reference. The last is feasible and its plug-in
Student-t probabilities are not assumed exact. Production stays FirstLevelModel;
bounded matrix references are synthetic diagnostic tools, never human fit engines.

Spatial stage:128 realizations each: Gaussian independent27/343 voxels;
AR(.6) independent27/343/1000; AR2 independent343; AR(.6) spatially correlated343;
AR(.6) smoothed343; AR(.6) signal/null mixture343 with prespecified effect1.
Stationary innovations after500 burn-in; explicitly fixed masks and independent
Gaussian innovations unless spatial filtering is declared. Save smoothing operator,
spatial covariance, true temporal covariance, exact design, contrast and sample/DF.
Use two-sided t probabilities and compare direct SciPy t with Nilearn signed-z
conversion. Compare BHq.05, BYq.05 and Bonferroni alpha.05 without treating a
conservative correction as a cure for invalid marginal probabilities.

Report marginal p histograms/QQ/KS diagnostics, coverage, SE calibration, selected
voxel rejection and global-null any-rejection with Wilson Monte Carlo intervals.
FDR under mixtures is mean FDP, not global-null family error. Record cluster sizes,
voxel-count/spatial sensitivity, estimated AR coefficients, tail-conditioned AR/SE,
residual ACF, nominal n-rank(X) and contrast-variance-equivalent effective sample
size. The latter is not automatically Student-t residual DOF. No exact finite-
sample t claim for estimated covariance; subtracting AR parameters alone is not
presumed a solution. Rank failures and nonfinite outputs are explicit.

Independent QR/precision equations, rho0 limits and the actual historical matrix
provide numerical oracles. Known-parameter conditional AR whitening/startup is
compared to exact stationary covariance, separately from covariance estimation.
Uniformity diagnostics are estimates with sampling uncertainty, not automatic
acceptance based on one KS p-value. Tests use fixed mathematical or broad Monte
Carlo criteria; no flaky narrow random thresholds or hardware timing limits.

## Candidate inference policy and human boundary

Default new policy is descriptive/experimental nominal maps. Existing effect,
variance and diagnostic APIs remain; old nominal threshold outputs are not silently
renamed as calibrated. Unsupported confirmatory requests must fail. A narrowly
supported class is fixed-design iid Gaussian temporal noise, independent fixed
voxel family, OLS and explicitly two-sided t/BH. Known-covariance GLS remains a
synthetic reference class, not an available human default. BY/Bonferroni require
valid voxel probabilities too. Evaluate the candidate, then seal the final policy
before any new human contrast result. No universal calibration claim.

Human ds000114v1.0.2 pilot remains the existing selected participant/test+retest
motor task; inspect actual inputs, events/metadata, field maps, derivatives and
confounds without fetching extra MRI. Run the established local official BIDS
validator on the untouched subset. No fabricated metadata or silent conversion.
Preprocessing requires adequate validation, a pinned available runtime/image,
architecture/memory/disk, local anatomical resources/TemplateFlow and applicable
FreeSurfer license. Inspect only; no silent image/template pulls, daemon startup
or expensive preprocessing launch. If unavailable provide an exact command with
explicit blockers and digest status. Write output/work separately, raw read-only.

After adequate preprocessing only: existing audits, visual HTML review, source
identities/timing/motion/transforms/masks, frozen nuisance and motor contrasts,
ROI/space correspondence and descriptive two-visit metrics. No cohort ICC from
one participant. Feasible AR human contrasts are descriptive unless independently
supported; no motor-execution/imagery equivalence. Missing derivatives or invalid
inputs remain unavailable, not simulated human results. Medical images, identifying
source hashes and individual results stay ignored; only aggregate code evidence
and documentation are committed.
