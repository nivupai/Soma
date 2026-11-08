# Source covariance and grid calibration

`source.priors.SourcePrior` holds N×1×1 fixed-moment or N×3×3 Cartesian covariance
blocks, explicit ordered source identities, MRI/HEAD basis and `(A m)^2` units.
Blocks must be finite symmetric positive semidefinite and nonzero in total.
Positive semidefinite rank-deficient orientation constraints are allowed; an
unobservable covariance cannot be normalized. Estimates remain dipole moments in
A m. Dense source covariance/resolution matrices are never constructed.

For whitened lead field G=W L and independent blocks Q_i:

* Uniform: Q_i=I (per-component moment variance convention).
* Depth: Q_i=d_i I, d_i=min(10,(max_j||G_j||F/||G_i||F)^(2*.8)). Zero-sensitivity
  blocks use a finite numerical floor; no truth depth enters the weighting.
* Area: Q_i=(a_i/.001 m²) I for density white noise integrated over patches.
* Orientation: Q_i=n_i n_iᵀ+.2(I−n_i n_iᵀ), for unit normals in the same Cartesian
  basis; fixed orientation already constrains the single normal coefficient.
* Combined: multiply area and depth variance factors.

`vertex_areas` computes one-third incident triangle areas from metre coordinates.
It rejects explicit non-metre units, degenerate patches and unused source vertices.
Units cannot be inferred from arbitrary numbers: callers retain geometry evidence.
A smooth common density coefficient has Q_moment=A Q_density A and differs from
independent density white noise with moment variance proportional to area. Neither
is interchangeable with uniform independent vertex moment variance.

M11 grids are volumetric points, so they have no measured cortical patch areas.
The area comparison explicitly uses equal quadrature 4π(.065m)²/N. This is a
controlled measure convention; no cortical anatomical area claim. Fixed directions
are radial synthetic normals. Free orientations are Cartesian. Off-grid truth uses
its own radial/30° vector, and this orientation prior need not fit true anatomy.

Optional sensor-trace normalization sets Q'=Q/tr(G Q Gᵀ), target trace 1.
Only this scalar property is guaranteed. Sensor covariance shape, prior total
variance, resolution gain and source recovery can still change with grid/prior.
For **every** grid/prior/normalization at a given representation/fitted-noise model,
alpha=lambda2*tr(G20mm G20mmᵀ)/rank is held fixed, using the uniform unnormalized
20-mm reference. lambda2=.01,1/9,1. This deliberately exposes changed effective
regularization under scaling. A target trace of 1 can strongly shrink moment
amplitude with this fixed physical alpha; this is retained as an unfavorable
result, not retuned away. Raw and normalized estimates cannot be compared without
this alpha convention.

K=Q Gᵀ(G Q Gᵀ+alpha I)^−1 W. alpha=0 uses the retained sensor pseudoinverse.
Rank-deficient noise uses existing NoiseModel whitening. Diagnostics save prior
trace, sensor spectrum/trace, kernel norm, tr(KL), and diagonal/selected PSFs.
Source IDs/order, basis, orientation, covariance and lead fingerprints are explicit.
Cached M10 physical forwards depend on anatomy, sigma, source positions, sensor
geometry, transform, software and builder hash; priors/kernels are recomputed.

Independent diagonal/low-rank oracles, triangle areas, basis rotations and scaling
laws test implementation. A public MNE comparison uses identical native forward,
average reference, rank23, free orientation, depth=None, Q=I and
alpha=lambda2*tr(G Gᵀ)/rank. This matches MNE's trace/rank source-prior scaling;
it does not claim the custom capped depth/area policies equal MNE depth=.8.
MNE reference: https://mne.tools/stable/documentation/implementation.html .
