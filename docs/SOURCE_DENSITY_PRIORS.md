# Source-density priors: M31

The coefficients j_i are integrated dipole moments in A m, with source-major XYZ
ordering. A current-moment density J(r) has units A/m², and j_i = ∫cell_i J(r) dr.
For the explicitly chosen spatial-white generalized field,
E[J_a(r)J_b(r′)] = q δ_ab δ(r−r′), q has units A²/m. Disjoint cells therefore give
Cov(j_i,j_k) = q V_i δ_ik I₃. This is not a finite pointwise variance smooth field.
A smooth, cellwise constant random density would instead give V_i² scaling and
possibly intercell correlations. Neither model is universally physiological.

All grids cover the same 65 mm radius ball. Approximate Voronoi cell volumes use
65,536 fixed unscrambled Sobol probes transformed to a uniform-volume ball, with
nearest-candidate assignment. Positive occupancy is required; total mass equals
the ball volume to numerical precision. These are deterministic quadrature
approximations, not certified exact Voronoi geometry. Sources remain point dipoles
at cell sites; no within-cell integration of the forward field is claimed.

M31 uses moment scale j₀ = 10⁻⁸ A m and reference count N₀ = 12. The diagonal
coefficient covariance is j₀² R, repeated for XYZ at each site:

- Historical unweighted: R_i = 1, trace = 3N j₀².
- Cell-volume white-density prior: R_i = N₀ V_i / Vdomain. This sets
  q = N₀ j₀²/Vdomain; trace = 3N₀ j₀² = 3.6×10⁻¹⁵ (A m)².
- Total-variance control: R_i = N₀/N, with the same fixed total trace. This is
  a numerical normalization. It approximates the volume prior only for equal cells.

The reference count and moment scale specify a controlled prior, not an inferred
human current intensity. Dividing by N is not generally a valid spatial prior.
All variances are strictly positive; covariance is diagonal positive definite.
Grid fingerprints bind every variance to the exact ordered source coordinates.
Invalid mass, nonpositive/nonfinite values, units, XYZ ordering, duplicate sites,
outside-domain coordinates and reordered grids are rejected. Operator inputs are
copied and immutable. No optional depth prior was added.

For retained-subspace whitener Q and forward G, A = Q G j₀ and B = A R Aᵀ.
The physical moment kernel is j₀ R Aᵀ(B+αI)⁻¹Q. Whitening excludes the average-
reference nullspace. All experiments use the fixed nominal covariance
(0.05 µV)²P, including noiseless and 0.15 µV measurements, to separate changing
actual noise from changing inverse assumptions.

MNE and dSPM retain MNE's intrinsic normalization R ← R·rank/trace(A R Aᵀ).
Consequently unweighted and total-variance controls produce identical MNE/dSPM
kernels for fixed α; global prior scaling cancels exactly. Cell-volume weighting
can change spatial shape and hence the sensor covariance spectrum. The independent
implementation is checked against MNE 1.13.2 and the unchanged historical code,
with maximum historical kernel relative discrepancy 1.652×10⁻¹³. Analytical tests
also solve coefficient-space normal equations independently of the sensor-space
implementation. The normalization is documented in
[MNE's implementation reference](https://mne.tools/stable/documentation/implementation.html).

dSPM divides each three-component moment block by its nominal noise standard
norm. Its values are dimensionless. Its resolution maps have units 1/(A m), not
physical current or the dimensionless moment-resolution units. Sensor prediction
uses the underlying moment kernel; normalized dSPM values are never fed through G
as if they were moments. Physical dSPM amplitude requests are rejected.
