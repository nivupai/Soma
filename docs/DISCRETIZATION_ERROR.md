# Discretization, quantization and uncertainty

The study separates analytic shape error, voxel sampling, finite surfel metrics,
source-grid quantization, BEM approximation, assigned boundary/registration errors,
noise and inverse regularization. These do not generally add linearly.

For the 30-mm analytic sphere, scalar-isosurface relative area error falls from
−0.559% at 4-mm voxels to −0.0349% at 1 mm; algebraic volume error falls from
−1.053% to −0.0661%. Radial vertex RMS falls 0.02536→0.00171 mm. Binary-mask volume
error also decreases (−2.592%→−0.166%), but its area error **increases**
6.302%→8.385%. A staircase boundary need not recover continuum area merely by
adding voxels. Ellipsoid/asymmetric references use independent high-order surface
quadrature and exact/independent volume formulas. No universal monotonicity claim
is inferred from selected favorable curves. Signed volume and radial residuals
retain their stated validity limits.

For the first continuous normal source with analytical fixed-radial reconstruction
at lambda²1/9, noise-free peak errors are 11.789/9.949/7.549 mm on 20/15/10-mm grids.
Nearest-grid distances are 11.789/9.949/3.315 mm. The remaining localization error
cannot simply be called geometric quantization, nor decomposed by subtracting
scalar distances as independent causes. Nearest-vertex moment ratios fall
0.2015→0.0754→0.01968 as the model grows. Greater spatial density does not imply
unbiased dipole amplitudes under an underdetermined point-moment prior.
Across all 72 prespecified noise-free source/angle/solver/representation/lambda
curves, 58 have at least one worsening peak-error step on refinement. Non-nested
15-mm sampling, orientation assumptions and regularized resolution all contribute;
this count is descriptive, not a population test.

The 1-mm inner-boundary perturbation, 1-mm translation and their combination are
physically recomputed on validated synthetic BEMs. On the 10-mm fixed grid their
relative lead-field changes are 5.401%, 1.073%, 5.529%; halving skull conductivity
changes it 29.161%. These assigned mathematical errors are not distributions of
human anatomy. The small boundary×registration peak-error interaction is zero
for all 20 paired draws at the chosen settings: no active peak switches occurred.
Degenerate sample intervals do not establish absence of interactions generally.

A supplemental all-group contrast uses only the prespecified solver/regularization
levels: (BEM−analytical at lambda²1) − (BEM−analytical at lambda².01). It includes
all 36 source/angle/grid/representation groups, without choosing winners. Mean
peak contrasts range −2.061 to +12.924 mm; paired 95% t Monte Carlo intervals are
saved. This measures numerical conductor-discretization×regularization interaction,
not biological variance decomposition. The reproducible postprocessor also records
nearest-current-ratio contrasts and its input/code hashes.

Monte Carlo intervals concern means over 20 independent noise snapshots, paired
across configurations, conditional on fixed geometry/source assumptions. They are
approximate small-sample t intervals; no anatomical credible interval, human-label
population interval or clinical generalization is claimed. Per-source depth and
orientation remain explicit. M9's severe distributed current attenuation and lack
of independent participant MRI fiducial truth are preserved, not declared fixed.
