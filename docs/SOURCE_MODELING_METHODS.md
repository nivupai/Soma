# Source modeling methods (v0.6.0)

The sealed [protocol](SOURCE_MODELING_PROTOCOL.md) preceded real source analysis.
This milestone demonstrates a mathematical method on template anatomy. It does
not identify the physical generators of participant 1's EEG.

## Geometry and anatomy

`geometry.Points` contains finite n×3 coordinates in metres and an explicit
`Frame`: head, MRI, template MRI, or device. Millimetres enter only through the
named conversion constructor. Template MRI and participant MRI are distinct.
Transforms use column vectors: x_destination = T_destination←source x_source.
Composition checks the intermediate frame; inversion solves a linear system.
Rigid transforms require a proper orthogonal rotation, positive determinant,
and homogeneous last row. The 5×10⁻⁷ absolute rotation tolerance admits the
roundoff in the supplied fsaverage FIF transform (maximum RᵀR discrepancy
2.59×10⁻⁷); it does not admit an anatomical scaling or reflection.

`Template` reads explicitly fetched MNE fsaverage assets. The root archive is
OSF version 2 and the BEM archive version 4; actual assets are identified by
SHA256, rather than an invented anatomical release number. We construct ico3
white-surface source spaces with MNE, without all-pairs cortical distances.
There are 642 vertices per hemisphere, 1,284 total. Surface files use mm;
MNE source/BEM coordinates use m. Sources retain hemisphere and FreeSurfer
vertex IDs through forward conversion, inverse STCs and saved maps.

EEGBCI labels are normalized by the existing adapter. The source workflow uses
`fsaverage_1005`, MNE's supported fsaverage transform and all 64 EEG channels.
The montage is template metadata, not digitization. Nearest scalp-vertex distance
is an approximate mesh diagnostic, not exact point-to-triangle distance or
coregistration accuracy. The montage's fiducial-derived native transform and the
supplied fsaverage transform differ slightly; their observed coordinate
agreement is recorded instead of asserting they are identical.

The physical forward uses `mne.make_forward_solution`: EEG only, the existing
three-shell 5120-triangle-per-shell fsaverage BEM solution, 5-mm minimum source
clearance, one job. Conductivities are read from the actual BEM and reported
with its checksum. No BEM mesh solver is reimplemented. See MNE's
[EEG without individual MRI tutorial](https://mne.tools/stable/auto_tutorials/forward/35_eeg_no_mri.html).

## Forward and inverse operators

For y in volts and signed dipole currents j in A m, y = L j + e.
The lead field has units V/(A m). Average reference P = I − 11ᵀ/C is applied
to L and the data; rank is at most C−1 = 63. Source count, channel order,
head coordinates, orientation basis, normal-column consistency, finite values,
singular spectrum and effective rank are checked. The retained condition number
describes nonzero singular directions; it is not evidence of a unique inverse.

The native MNE forward keeps three local surface basis directions per vertex.
The primary inverse constrains currents to signed white-surface normals, with
`use_cps=False`. Fixed columns equal every third (normal) free-basis column.
Depth-weighted fixed inverses must be constructed from the free surface-oriented
forward; converting to a fixed forward first discards information required by
MNE's depth prior. The adapter follows the documented
[orientation/depth rules](https://mne.tools/stable/generated/mne.minimum_norm.make_inverse_operator.html).
A free-vector inverse is also supported. MNE vector STCs use Cartesian head
components; the kernel adapter rotates these back into the forward's local
surface basis. Taking vector magnitudes is nonlinear, so a magnitude map must
never be passed off as having the same fixed linear resolution kernel.

The anatomical solver is MNE's minimum norm implementation, with depth exponent
0.8 and λ² = 1/9 fixed before the experiments. It normalizes the source prior
and whitened lead field; this λ² is not the dimensional penalty of an arbitrary
raw lead-field matrix. MNE estimates are A m; dSPM divides by modeled noise
sensitivity and is dimensionless. Their power units are (A m)² and
dimensionless² respectively. dSPM cannot be forward-projected as physical current.

The independent small-matrix `Tikhonov` reference solves
‖Q(Lj−y)‖² + λ²‖j‖² via SVD, with filters s/(s²+λ²). With λ²=0 it uses a
rank-aware pseudoinverse. It never explicitly forms an inverse of a normal
matrix. It is an educational numerical oracle, not an alternative anatomical
inverse solver. Tests and numerical tables distinguish identifiable exact
recovery from minimum-norm recovery of an underdetermined system.

## Covariance, whitening and reference

`NoiseModel` validates symmetry, positive semidefiniteness, channel identities
and the explicit reference/SSP projector. Negative eigenvalues beyond roundoff
are rejected. Shrinkage targets a scalar multiple of the retained projector,
so it cannot restore the average-reference null direction. For C = UDUᵀ, the
rectangular Q = D_retained⁻¹ᐟ² U_retainedᵀ obeys Q C Qᵀ = I on retained
coordinates. Null eigenvalues are reported and dropped, never silently inverted.
The full inverse validates MNE covariance projector definitions and uses its
measured retained rank. General projector math is supported by `NoiseModel`;
the fsaverage workflow explicitly uses average reference only.

Real covariance comes from accepted same-run T0 epochs, using
`mne.compute_covariance(method='shrunk')` with the single predeclared shrinkage
0.1, not a grid selected from outcomes. Filtered rest epochs retain their means;
MNE's warning about absent baseline correction is preserved. This covariance
contains background neural activity and possible artifacts, not an independently
measured instrumental noise floor. Real rest-power normalization and covariance
training reuse these rest epochs; they are descriptive, not independent tests.
Synthetic covariance training uses 16,000 separate noise samples and a disjoint
seed stream. Evaluation noise has the same specified correlation family but
independent samples. Controlled SNR uses truth only to scale simulated noise;
it never chooses λ², depth, vertices, or an estimator by recovery accuracy.

## Resolution and sensitivity

For a fixed signed linear estimator W, K = W L. `Resolution` computes selected
columns (PSFs), selected rows (CTFs), the diagonal, or matrix-free products.
The full cortical K is not allocated. Twelve predeclared sources and five λ²
values are retained, without selecting a favorable λ². Peak distance uses
|PSF|; dispersion and leakage use squared amplitudes. Metrics report Euclidean
head distances separately from within-hemisphere shortest paths along the full
white mesh. Edge shortest paths approximate a surface geodesic. Cross-hemisphere
geodesics are undefined (infinity in NPZ, null peak geodesic in JSON); energy in
the other hemisphere is reported separately.

The simulation includes focal, separated, correlated, shallow/deep, amplitude
modulated, burst, and forward-mismatch currents. NeuroDSP generates the 10-Hz
carrier; envelopes, current amplitudes, phases, source IDs and noise seeds are
explicit. Shallow/deep selections use nearest scalp-vertex clearance, a geometric
proxy, not cortical thickness. Ten paired noise realizations at −10/0/10/20 dB
produce 280 cases. Multi-source peaks use a predeclared 20-mm exclusion radius
and distance assignment; this heuristic can miss a weaker second generator.
Report its errors rather than calling every two-peak result successful recovery.
Current error, amplitude bias, residual, time-course correlation and dispersion
supplement peak localization, which alone can hide enormous leakage.

The 5% lead-field perturbation is an abstract operator stress, not a physically
recomputed BEM conductivity. A separate four-shell analytical MNE sphere control
reconstructs conductors at skull conductivities 0.004 and 0.012 S/m and recomputes
both forwards. Its four Cartesian-vector sources and 13 sensors are not the
fsaverage BEM. Sensor column-subspace angles are nearly zero here because the
12-dimensional referenced sensor subspace is saturated; they are uninformative
about individual source correspondence. Matrix and spectrum changes, estimate
sensitivity and peak displacement remain useful distinct measurements.

## Real oscillatory reconstruction

Subject 1, runs 4/8/12 reuse the existing EDF adapter, duration-aware event parser,
continuous 1–40-Hz zero-phase Butterworth processing, QC and half-open [1,3)-s
trial windows. QC thresholds are unchanged; flagged channels are reported,
not automatically interpolated or dropped. Epoch generators apply MNE/dSPM to
each accepted trial with nave=1. Batched NeuroDSP Welch uses 1-s windows and
50% overlap; mu is 8–13 Hz and beta 13–30 Hz. Mean vertex powers are computed
within condition/run. Log ratios of condition mean powers to T0 mean powers
are averaged equally over the three runs. The explicit numerical floor prevents
logarithms of zero; it is in the correct method-specific power units.

Available fsaverage aparc precentral labels define descriptive template ROIs.
An ROI averages vertex powers, not signed waveforms from opposing cortical
normals. Atlas files are hashed in the results. No vertexwise population test
or contralateral localization claim follows from these data.

The evoked comparison pools all accepted T0/T1/T2 trials equally, reconstructs
the mean waveform with exactly the same nave=1 operator, and checks equality
with the mean reconstructed waveform. Its power is compared with mean individual
trial power. This isolates averaging effects, but the real comparison alone is
not proof of neural phase cancellation: noise also averages away and conditions
are pooled. A separate analytical opposite-phase sinusoid test demonstrates
cancellation while preserving induced power exactly.

## Boundaries and computation

Anatomical assets, raw recordings, caches and full report arrays remain outside
Git. Native FIF caches are staged then atomically replaced; an atomic checksum
receipt is published last. Missing/mismatched receipts fail closed. Cache keys
bind anatomy/source hashes, builder and template adapter code, MNE/NumPy versions,
montage, channel order, spacing and clearance. Signed/free selection and projector
are deterministic, revalidated after reading. Result manifests additionally record
the entire source tree hash, configuration, versions, Git state and output hashes.
A partial report directory is not reusable; choose a new output path.

Lead fields cost O(CN) memory (three times for free orientation); sensor-space
factorizations are bounded by C, and inverse application is O(NCT). Trial-wise
streaming bounds time-course memory; saved trial-power arrays are O(trials×N).
Mesh geodesics use sparse edges and one seed at a time, rather than all-pairs
surface distances. No GUI or 3D renderer is needed for computation or figures.

A future participant-MRI adapter can supply validated source spaces, BEMs,
electrodes and a head↔participant-MRI transform to the MNE boundary while retaining
vertex IDs, units, covariance/projector contracts and inverse APIs. Template MRI
cannot be silently substituted for participant MRI. Registration, segmentation,
FreeSurfer reconstruction, FEM and anatomical validation remain future work.

## Participant extension (v0.8.0)

The formerly prospective participant boundary is now implemented conditionally
by `source.individual`; the original template APIs and sealed M6 protocol remain
unchanged. The matched sample uses individually digitized retained electrodes,
participant white ico3, three FLASH-derived conductor boundaries, and the
existing fixed-normal MNE inverse. No fsaverage substitution is allowed.
The audiovisual signal example uses code 1/2/3/4, not EEGBCI task labels.
Prestimulus covariance includes background activity; short-epoch trialwise power
is separate from phase-locked power. Conductivity and geometry sweeps recompute
physical forwards with fixed inverse settings and independent noise training.
See INDIVIDUAL_SOURCE_VALIDATION.md and ANATOMICAL_UNCERTAINTY.md for the
unfavorable recovery, substantial BEM discretization error and anatomical limits.

## v0.9.0 inverse reliability

The historical true-vertex RMS amplitude ratio is valid for signed MNE currents
in A m. Selected W L columns explain its strong attenuation; peak amplitude,
signed waveform transfer, pooled vector magnitude and distributed energy are
separate definitions. The new `reliability.inverse` adapter supports MNE/dSPM/
sLORETA without changing `CorticalInverse`. Normalized-statistic transfers have
statistic/(A m) units; no physical amplitude/residual comparison is made for them.
Fixed/loose/free vectors retain their basis, channel and source identities.
See INVERSE_CALIBRATION.md for regularization/depth, independent exact oracles,
selected PSF/CTF operations and the unfavorable recovery retained in full.
