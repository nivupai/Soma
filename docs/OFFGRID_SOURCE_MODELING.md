# Continuous dipoles and inverse-crime safeguards

`ContinuousDipole` requires one identified MRI-frame physical location, explicit
unit orientation and positive moment in A m. It does not derive truth from a
reconstruction column. The forward path evaluates MNE at these explicit locations;
source order/frame return checks and a >0.5-mm noncoincidence assertion guard the
separation from reconstruction vertices. Subject/frame/orientation mismatches
fail. No interpolated grid lead field is called independent forward evaluation.

The synthetic reference has 24 fixed EEG sensors, average reference, 80/85/90-mm
shells and assumed brain/skull/scalp conductivity 0.3/0.006/0.3 S/m. Three continuous
positions span depths, with normal/radial and 30-degree off-normal orientations.
Reconstruction grids are 20/15/10 mm (146/340/1,188 locations), each with fixed
radial or free Cartesian source representations. These mathematical radial priors
are not measured cortical normals. The 15-mm grid is not nested in the other two;
quantization bounds therefore need not be monotone at every step.

Five explicitly distinguished situations are recorded: same-grid operator-column
control; off-grid/shared analytical conductor; off-grid analytical truth versus
triangulated BEM; registration geometry mismatch; boundary/conductivity conductor
mismatch. The same-grid control reproduces resolution gain 0.1087207 and is
explicitly **not** independent validation. All primary truth is separately
computed at continuous locations. Both solvers share spherical, isotropic,
piecewise homogeneous assumptions; MNE's analytical reference itself uses an
established approximation. BEM also projects EEG contacts to its faceted scalp.
Thus off-grid/distinct discretization does not imply fully independent physics or
isolate a single continuum discretization error. No inverse-crime-free anatomical
claim is made merely from changing a source grid.

The synthetic inverse reuses the independently validated small-matrix Tikhonov
solver, with scale ||L||F/sqrt(retained rank) and prespecified lambda² .01/1/9/1.
Actual scale, physical ridge alpha, rank, condition and noise amplification are
saved. Source coefficients are point-dipole moments, not voxel-volume-normalized
current densities; density changes affect the prior and amplitude attenuation.
The nearest-vertex current norm/true moment is descriptive off-grid recovery,
not a claim to estimate current at a location absent from the model.

Twenty paired projected-white Gaussian sensor snapshots at expected 10-dB SNR,
plus noise-free controls, reuse common seeds across grids/operators. Report peak
point error, nearest-grid distance, dispersion, leakage, nearest-vertex amplitude
ratio and sensor residual. Every peak satisfies its nearest-grid geometric lower
bound; that bound does not apply to a continuous centroid estimator.

## Conditional participant BEM

The MNE sample example independently places dipoles at MRI [-.04,-.02,.05] and
[.02,0,.01] m, checks containment and separates them from white ico2/ico3 vertices.
It uses the actual 59-channel participant EEG/BEM and MNE fixed/free inverses with
depth .8, lambda²1/9 and independent covariance training. Normal direction is
explicitly borrowed from the nearest ico3 cortical vertex and tilted for the
off-normal cases; an off-surface dipole has no measured cortical normal. Thirty-two
rows cover both positions/orientations/representations/grids and noise conditions.
The continuous forward is an actual new MNE BEM evaluation, not a grid column.
This shares the conductor and remains conditional: real anatomical readiness is
INDETERMINATE. No EEG is fabricated for BrainWeb or Mindboggle.
