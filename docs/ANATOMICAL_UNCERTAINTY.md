# Anatomical uncertainty experiments

The study measures sensitivity of L(G, σ, T), not a posterior distribution over
this person's anatomy or tissue conductivities. Sources/sensors are held in
explicit physical correspondence. Comparisons reject different channel order,
vertex IDs, orientation conventions, physical source positions or participants.
A change in tissue conductivity rebuilds the MNE conductor solution and forward;
no conductivity experiment rescales an existing lead-field matrix.

The frozen configurations contain all physical scales. Alternatives to baseline
0.3/0.006/0.3 S/m are scalp-low 0.24/0.006/0.3, skull-low 0.3/0.003/0.3,
skull-high 0.3/0.012/0.3 and brain-high 0.3/0.006/0.36. Channel-specific relative
changes and singular spectra accompany full Frobenius changes. These assumed
values are not identified from the data. No independently distinct, validated
alternative participant anatomy with corresponding sources was available.

Central derivatives use [L(+h)−L(−h)]/(2h). Translation and one-electrode x steps
are 1/0.5/0.25 mm, rotation z steps 1/0.5/0.25 degrees (derivatives per radian),
skull conductivity steps 0.0006/0.0003/0.00015 S/m. All three derivatives and
step-to-step differences are saved. Translation/electrode derivatives on this
small setup are nearly exact within the local barycentric regime; rotation
changes about 2.1% at the finest comparison because mesh projection can change
triangles. Conductivity changes about 0.06% at the finest comparison, with
approximately second-order improvement. These observations do not justify
smoothness or linearity for arbitrary geometry errors.

For a scalar 0.2-mm translation SD, J Cθ Jᵀ predicts sensor covariance on the
small sphere. Twenty independent seeded parameter draws give an empirical to
predicted variance ratio 1.62874. Their realized parameter variance has exactly
the same ratio; the Gaussian finite-sample 95% ratio interval is [0.4688,1.7291].
Conditioning the covariance prediction on that realized parameter variance leaves
relative error about 2.44e-13; realized forward linearization error is 3.32e-13.
The raw covariance discrepancy 0.62874 is retained rather than hidden. This is a
local numerical check with limited Monte Carlo precision, not population coverage.

The participant mismatch study generates 10-Hz, 10-nA m fixed-normal current at a
prespecified geometric nearest vertex and expected sensor SNR 10 dB. Independent
10,000-sample colored-noise training estimates covariance. Evaluation noise and
20 independent sensor-noise draws use separate seeds. The fixed MNE inverse
uses depth 0.8, lambda²=1/9, nave=1 and no CPS; truth never selects regularization.
Source variance is variance over those sensor-noise draws at fixed geometry,
not variation over anatomical uncertainty. Correct, pose, electrode, conductivity,
fiducial and headshape models all reconstruct the same generated measurement.

Metrics include peak Euclidean error, current bias, spatial energy dispersion,
off-target leakage, residual and variance. A mismatched model's better peak can
be accidental given the broad inverse point spread; it is not evidence for that
anatomy. Negative controls are retained as rejected or failed inputs. Fixed-seed
uncertainty and noiseless spherical source recovery have offline regression tests.
See [results](INDIVIDUAL_SOURCE_VALIDATION.md) for all limitations and observed values.
