# MRI registration methods

Soma uses SimpleITK for optimization and its own explicit geometry adapters,
independent physical error metrics and experiment orchestration. Registration
completion is a numerical event, not an anatomical correctness claim.

## Coordinate and array boundary

NiBabel arrays are indexed (i,j,k); SimpleITK's NumPy interface uses (k,j,i).
`to_sitk` transposes array axes, obtains spacing from affine column norms, and
sets physical origin and direction from the affine. Internal RAS metres become
SimpleITK LPS millimetres through `diag(-1,-1,1)` and ×1000. A negative storage
axis remains part of direction. Sheared image grids are explicitly rejected at
this boundary: callers must first resample onto a justified orthogonal reference
grid. They are not silently decomposed into an approximate direction matrix.

The inverse adapter recovers array ordering and the complete RAS-m affine. It
preserves dtype. Tests use independently transformed physical index points,
rather than validating only a round trip that could hide a shared axis error.

SimpleITK registration maps fixed physical points into moving physical points;
this is the pull transform needed to sample moving intensities on a fixed grid.
The returned Soma matrix is explicitly **fixed RAS m → moving RAS m**.
[SimpleITK's registration overview](https://simpleitk.readthedocs.io/en/master/registrationOverview.html)
defines this direction. Moving-to-fixed is its inverse, not the same matrix.

To recover a global affine, the adapter evaluates the transformed origin and
three independent basis points in native LPS-mm coordinates. This accounts for
rotation center, translation and composite transforms without assuming that a
parameter vector is a homogeneous translation. Additional independent probes
reject a non-affine result. Both native `.tfm` and RAS-m JSON matrices, grid IDs,
settings and optimizer trace are serialized. `RegistrationResult.warp` checks
the fixed/moving grids; subject correspondence is a separate scientific question.

## Implemented models and optimization

Rigid Euler3D and general 3D affine models are supported. The recorded default
experiment configuration uses all voxels, mean-squares metric, linear sampling,
300 regular-step gradient-descent iterations per pyramid level, learning rate
1 mm, minimum step 0.0001 mm, relaxation 0.5, gradient tolerance 1e-8 and
physical-shift parameter scaling. Shrink factors are 4/2/1 and physical smoothing
sigmas 2/1/0 mm. Full sampling avoids random metric sampling and gives deterministic
small experiments. Correlation and Mattes mutual information (40 bins) are also
configurable; the measured primary acceptance benchmark uses mean squares.
One ITK/BLAS thread is used in the verified workflows.

Initialization may align geometric centers, align raw nonnegative intensity
moments, or use identity. Metric normalization subtracts the mean and scales by
standard deviation in float32. Intensity-moment initialization deliberately
uses raw intensities, because zero-sum normalized images have meaningless intensity
centroids. Negative raw intensities are rejected for moment initialization.
Constant and nonfinite images are rejected. Identity initialization is available
for controlled failure studies and is not a promise of convergence.

The report preserves settings, final metric, stop description, total recorded
iterations, per-level trace, final valid-voxel count/fraction, runtime and native
library version. Fewer than 10% valid fixed-grid voxels is rejected. A stop caused
by the iteration limit is distinguished from a small-step stop. Neither implies
valid anatomical alignment; intensity ambiguities and poor overlap can produce
plausible losses with large physical errors.

## Independent synthetic acceptance

The primary asymmetric phantom has four Gaussians with different centers,
intensities and widths, sampled anisotropically at 2/2.5/3 mm. Known transforms
are built independently using SciPy rotations and explicit affine matrices.
Moving phantoms are evaluated directly from the transformed analytic functions,
not generated solely by the production resampler. Noise, intensity bias and
physical Gaussian blur are supported and seed controlled; their deterministic
behavior is tested. The main recovery table uses the noiseless asymmetric case.

The fixed small-perturbation grid tests multipliers 0.5/1/2 for rigid and affine
models with unchanged optimizer settings. Independent target-registration error
(TRE) evaluates the mathematical centers; translation and polar-factor rotation
errors separate affine scaling/shear from rotation. Thresholded analytic-region
Dice, MSE improvement and physical inverse consistency supplement TRE.
For multiplier 1, a separately optimized reverse registration also measures
inverse consistency; algebraically composing a transform with its own inverse
is not used as the sole registration accuracy test.

Pre-recorded acceptance is median TRE <1 mm for rigid and <1.5 mm for affine,
and rotation error <1°. These limits apply to the selected controlled phantoms,
not arbitrary scans or clinical anatomy. Constant images, severe perturbation/
poor initialization and a rotationally ambiguous sphere are retained as failure
or ambiguity cases. They are not removed or retuned to improve the primary table.

## Real-image controlled experiment

The SPM auditory T1w image is resampled onto a defined 3-mm grid, transformed
with a known rigid map, and registered back. This measures recovery of an
artificial motion on one subject's image. It is not validation of cross-subject,
multimodal, clinical, or actual EEG-to-MRI registration. Physical test points
span the image center but are not manually annotated anatomical landmarks.
Their identity and true transform are explicitly saved. Repeated interpolation
is acknowledged and source files remain untouched.
