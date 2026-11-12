# Milestone 26: anatomical uncertainty and known-source validation

Soma v0.26.0 produces a frozen, reproducible physical sensitivity study on an
idealized four-shell head. These are new quantitative synthetic results, not
human anatomical/source validation. No human data, anatomy or fitted weights
were acquired, fitted or localized by these experiments. Existing cached integration
tests were rerun unchanged. All earlier estimators/tests are preserved.

## Baseline and freeze

PR #10 merged at `5912057928a305ed0717886cf975512b745f7861`. The final PR run
43084127441 and post-merge run 43086286921 both passed all 13 jobs. Local/remote
main agreed, the checkout was clean, PUBLIC visibility was verified, and all
1,487 preserved Python tests passed before implementation. No visibility change
was made. See [current public policy](PUBLIC_RESEARCH_POLICY.md).

The numerical design was committed before final outcomes in `948d755`.
Its SHA-256 is `42a9608377c35577001ca4c216c82aaf40836f03eca869232ab8f5f461e37a8a`;
the M19 protocol fingerprint is
`9c4b348afb5507a101d7212df722cfe88b993e211ea5952a50ecf0e433f412ef`.
See the [frozen protocol](SOURCE_UNCERTAINTY_PROTOCOL.md) and public native seal.
This local record is not independent preregistration.

## What was actually simulated

| Quantity | Executed scope |
|---|---|
| Truth anatomy | One fixed synthetic spherical head, no participant MRI |
| Conductor | Fresh conductivity-aware MNE four-shell sphere, not template BEM |
| Brain/CSF/skull/scalp radii | 81 / 82.8 / 87.3 / 90 mm |
| Baseline conductivities | 0.33 / 1 / 0.004 / 0.33 S/m |
| Sensors | 32 independently defined synthetic cap positions |
| Inverse grid | 48 locations × 3 Cartesian current components |
| Independent truth generators | 12 off-grid location/orientation draws, 10 nA m each |
| Noise | Projected Gaussian, 0 / 0.05 / 0.15 µV per-channel pre-reference SD |
| Distinct measurements | 204: one noiseless + 8 draws at each noisy level per source |
| Planned configuration rows | 49, containing 45 distinct physical parameter settings |
| Methods | Existing Tikhonov, MNE and dSPM; frozen regularization |
| Planned reconstruction rows | 29,988; shared measurements do not increase independent N |
| Computed / failed rows | 24,480 / 5,508 |
| Accepted / rejected configuration rows | 40 / 9 |
| Human participants | 0 |

The inverse never generates its own validation measurements. Truth forward fields
use separate off-grid dipoles. Shared MNE forward code remains a limitation:
independent locations avoid the exact-grid inverse crime but do not establish an
independent physical solver. A separate linear solve verifies the SVD inverse;
MNE application verifies the existing MNE kernel adapter.

The frozen perturbations cover inner/outer skull boundaries up to 1/2 mm,
skull conductivity 0.002–0.02 S/m, electrode RMS offsets 2/5/10 mm with three
patterns, and signed x translations/z rotations up to 10 mm/10°. A 2^4 joint
factorial uses outer-boundary +2 mm, skull 0.01 S/m, electrodes 5 mm and translation
+5 mm. No settings were retuned after examining accuracy or failures.

## Localization and uncertainty

At 0.05 µV noise, means and 95% source-cluster Monte Carlo intervals are:

| Inverse | Baseline peak error (mm) | Spatial dispersion (mm) | Peak current bias |
|---|---:|---:|---:|
| Tikhonov | 27.689 [24.910, 30.211] | 46.925 | −82.74% |
| MNE | 27.574 [24.966, 30.117] | 42.897 | −89.36% |
| dSPM | 18.657 [15.669, 21.797] | 42.183 | Not physical: dimensionless |

Intervals resample the 12 independent generator draws after averaging noise draws
within each generator. They are conditional on one idealized head and frozen
parameterization, not human-population confidence intervals. They do not treat
paired measurements, methods or configurations as independent participants.
These nominal percentile-bootstrap intervals use only 12 generators; coverage
is not calibrated and they are not an anatomical parameter posterior.
Peak current bias describes a distributed reconstruction's largest vector current,
not total current recovery. dSPM's normalization prevents a physical amplitude
comparison. No method was selected from these outcomes.

All methods for representative perturbations at the same noise level:

| Estimated model | Tikhonov error (mm) | MNE error (mm) | dSPM error (mm) |
|---|---:|---:|---:|
| Baseline | 27.689 | 27.574 | 18.657 |
| Outer skull +2 mm | 29.013 | 27.052 | 17.821 |
| Skull 0.01 S/m | 28.558 | 27.052 | 17.821 |
| Electrode RMS 5 mm, pattern 0 | 29.911 | 28.919 | 18.766 |
| Translation +5 mm | 28.948 | 28.135 | 18.419 |
| Rotation +5° | 27.950 | 27.566 | 18.415 |

All source/noise rows, class-free physical metrics, paired excess-error intervals
and other conditions are retained in [the numerical tables](../experiments/milestone26/summary.csv).
The illustrative pattern is not an optimized selection. Some mismatches reduce
peak-grid error slightly: operator mismatch is not equivalent to monotonic peak
error, especially with a biased, regularized, coarse-grid inverse.

At 0.15 µV noise baseline mean errors are 46.893/30.165/19.526 mm for
Tikhonov/MNE/dSPM. In the noiseless baseline they are 26.823/27.284/17.793 mm.
Doubling the frozen candidate grid to 96 gives 20.010/19.965/12.735 mm without
noise; mean nearest-possible grid distance changes from 15.251 to 10.505 mm.
Grid resolution and inverse priors materially limit the experiment. These
results do not identify a universally superior method or dominant source of
error in actual humans.

## Failures, interactions and numerical limits

The ±10 mm translations and all three 10 mm electrode patterns place sensors
inside the innermost estimated shell. Four factorial high-boundary/high-conductivity
cells fail the frozen equivalent-source fit tolerance: RV ≈0.629957 versus a
maximum fractional RV of 0.001. Each rejected configuration retains 612 failed
rows. No rows are dropped, no missing values are imputed, and no tolerance or
geometry is changed to rescue the cases.

Full four-factor decomposition and boundary×conductivity contrasts are therefore
NOT_ESTIMABLE. Estimable MNE differences-in-differences at 0.05 µV include
boundary×electrode +0.535 mm and electrode×translation −0.353 mm. These are
conditional point contrasts, not significance tests or additive variance
components. Noise and grid sensitivity are reported separately.

Maximum inverse normal-equation residual is 5.58e−15 and independent linear-solve
relative discrepancy 3.39e−14. Valid forward rank is 31; retained condition numbers
range 19.49–77.87. Finite-difference step halving still changes the derivative by
5.53% at the last pair, so no converged derivative certificate is claimed.
The sphere approximation residual is not a finite-element PDE residual.
See [anatomical propagation](ANATOMICAL_ERROR_PROPAGATION.md),
[conductivity](CONDUCTIVITY_SENSITIVITY.md) and
[electrode/registration analysis](ELECTRODE_REGISTRATION_SENSITIVITY.md).

## Resources, reproducibility and limits

The final local run took 5.023 s after imports, with a whole-process peak RSS of
303.33 MiB including imports. The 32×144 baseline lead field occupies 36 KiB;
the 96-location version occupies 72 KiB. Two timing points are descriptive,
including cold/warm overhead; they do not establish a runtime scaling law or
per-case peak memory. All eight scientific figures are public SVG; PDF and PNG
verification copies remain local. [Resource figure](../experiments/milestone26/figures/resource-scaling.svg).

The first numerical attempt reached its tables but rejected unsupported generic
conductivity-unit metadata in the result envelope. That serialization was fixed;
the final repeat used the identical frozen physical design, ranges, tolerances
and exclusions. Both attempts remain in ignored receipts. Conductivity units are
explicit in named parameters/tables; the shared unit registry was not weakened.

The MRI, BEM, electrode, inverse and calibration audit reused the existing
conductivity-aware sphere and inverse operators. No real-anatomy benchmark was
silently promoted to BEM validation. Poor historical IBSR CSF results, unvalidated
skull/scalp boundaries, real conductivity/anisotropy, empirical coregistration,
clinical localization truth and cross-head sampling remain gaps. MRBrainS was
not used. No new infrastructure framework replaces the scientific experiments.

The [verification addendum](MILESTONE26_VERIFICATION.md) records local and remote
release gates. No Milestone 27 work is included.
