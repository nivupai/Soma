# Inverse estimator calibration

## Historical metric audit

The original M8 experiment generates a signed fixed-normal 10-nA m, 10-Hz source
at index 281 (lh vertex 71803). It estimates physical current using MNE depth 0.8,
lambda²=1/9, nave=1, no CPS. Its metric is
`||jhat[281,:]||₂ / ||j[281,:]||₂ - 1`: unsigned temporal RMS attenuation at the
true vertex. Both numerator and denominator have A m units. This is valid, but
is not signed waveform transfer, total reconstructed current, peak-source
amplitude, distributed power or a noise-normalized statistic. It remains
historical evidence rather than an invalidated result.

Reusing the original saved truth/measurement and independently regenerated
training covariance reproduces **−0.989671361410299** exactly. The selected
resolution prediction K=W L gives K[281,281]=**0.01024462555288556**, matching
noise-free current recovery to relative error below 9e-16. Direct MNE application
and the extracted kernel agree exactly in this run. Thus resolution attenuation
explains the approximately 99% single-vertex bias without a unit correction.

Signed waveform transfer with original noise is 0.0102422495063. The coherent
noise contribution is −2.37605e-6. Orthogonal noise energy divided by true waveform
energy is 1.77710e-6; squared RMS recovery equals squared signed transfer plus
that orthogonal energy (identity residual about 6e-21). Noise slightly increases
the unsigned norm here. It does not explain away the dominant attenuation.

## Methods and representations

The new adapter delegates full anatomical inverses to MNE's actual MNE/dSPM/
sLORETA implementations. It adds independently keyed kernels without changing
the earlier `CorticalInverse` API. Fixed sources are signed normal components.
Loose=0.2 and free=1 outputs are retained as linear vectors, converted from MNE's
Cartesian output back to the forward's surface-local basis. Their pooled norms
are nonlinear and explicitly separate from signed normal transfer.
[MNE documents these orientation and normalization conventions](https://mne.tools/stable/generated/mne.minimum_norm.apply_inverse.html).

MNE output is A m. dSPM/sLORETA output is a dimensionless normalized statistic.
Their kernel transfers therefore have units statistic/(A m), not dimensionless
physical current gain. Physical amplitude ratios and sensor residuals are omitted
for normalized statistics. Pattern cosine, peak location and energy dispersion
remain available with declared representations. No cross-method amplitude ranking
or universally best estimator is asserted. An opt-in test checks unit variance
of fixed dSPM under the assumed training covariance; it does not claim calibration
under every rescaled evaluation-noise level.

## Selected resolution and regularization

The sweep has 90 settings: three methods × five lambda² values
[0.0001,0.001,0.01,1/9,1] × three orientation assumptions × two depth weights
[0,0.8]. Three source indices are chosen geometrically before observing estimator
recovery: historical 281, deepest 858 and shallowest 621 under exact inner-skull
triangle distance. There are 270 source/setting rows and no rejected settings.
The separate MNE-only resolution command has 30 settings/90 rows.

K is applied through W(Lj). Selected PSFs are W L[:,I], selected CTFs W[I,:] L;
diagonals are row/column contractions. Neither routine allocates a full dense K.
Noise variance is diag(W C Wᵀ), and singular attenuation is s²/(s²+lambda²) in
MNE's whitened/prior-scaled singular basis. Stored inverse-cache receipts include
those spectra; raw lead-field singular values have V/(A m) units and must not be
confused with the whitened singular values. Exact small diagonal Tikhonov oracles
verify attenuation, leakage, variance and theoretically monotone regularization.

For historical fixed/depth0.8 source 281, gain ranges from 0.013884 at lambda²
0.0001 to 0.006688 at lambda²1. Smaller regularization improves noiseless sensor
residual but does not give unbiased vertex recovery. Rank is only 58 for 1,239
sources. At the primary lambda, gains at deepest/historical/shallowest vertices
are 0.003094/0.010245/0.041303; noise-free MNE peak errors are approximately
52.89/28.31/0 mm. sLORETA peaks at the generating vertex for these particular
noise-free controls, with broad dispersion and nonphysical amplitude statistics.
These few on-grid controls are not a universal localization or anatomical claim.

The depth audit also found a source only 0.676 mm from a triangle despite the
5-mm MNE vertex-based filter. No source space was changed. See the explicitly
[additional finding](MODEL_RELIABILITY_ADDITIONAL_FINDINGS.md).
