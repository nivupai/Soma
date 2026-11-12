# Conditional nonspherical source uncertainty — Milestone 27

Six independent generated heads, twelve independent off-grid source draws/head,
32 sensors and three inverse methods give 72 source generators. Each head has
one noiseless vector/source and eight draws at each pre-reference noise SD of
0.05/0.15 µV. There are **1224 unique measured vectors**, reused across meshes,
perturbations and methods. Noise draws are repeated measurements, never extra
heads or independent source generators. The inverse has 48 common positions
and 144 free Cartesian components. Mean nearest-grid distance is 14.893 mm
(range 4.733–24.723 mm), a substantial representational limitation.

Tikhonov lambda2 is .001 after one finest-baseline spectral scale per head.
MNE/dSPM use lambda2 1/9, free orientation, no depth weighting and the existing
validated M26 implementations. No regularization is chosen using held-out
localization outcomes. dSPM amplitude is normalized and never treated as A m.

| Method | L2 mean peak error at 0.05 µV (mm) | Conditional 95% interval | Dispersion (mm) | Peak moment bias ratio |
| --- | ---: | --- | ---: | ---: |
| Tikhonov | 20.795 | [18.642, 23.100] | 41.557 | −.762 |
| MNE | 20.929 | [18.982, 22.946] | 40.627 | −.873 |
| dSPM | 20.999 | [18.882, 23.206] | 42.154 | Not physical |

At level 0, peak errors are 40.715 / 36.113 / 24.759 mm in the same method order.
At 0.15 µV and level 2 they are 32.240 / 22.814 / 21.851 mm. The matched new
spherical control at 0.05 µV gives 20.718 / 20.923 / 20.936 mm. It shares the
M27 grid, source/moment/noise schedule but uses its own clean spherical voltages.
It is not the historical M26 measurement set. Historical dSPM 18.657 mm is an
unmatched conditional result, not a paired effect or human accuracy benchmark.

The modest prespecified anatomical/acquisition perturbations shift mean peak
errors by −0.069 to +0.218 mm at 0.05 µV. Registration increases MNE peak error
by .196 mm (conditional interval [.027, .411]); doubled skull conductivity changes
Tikhonov by .183 mm [−.258, .759]. These small, grid-dependent effects do not show
that anatomy or conductivity is unimportant. Peak selection is discrete; fields,
spatial spread, amplitude and resolution can change without a changed peak.
`resolution.csv` evaluates linear PSFs at all 48 positions × three orientations,
using Soma's existing Resolution API. Vector magnitude is calculated after the
linear PSF; it is not called a fixed linear magnitude kernel.

Uncertainty averages noise within source, resamples heads within each fixed
family, then sources within head, using 1999 deterministic bootstrap draws.
Identical resampling indices define paired contrasts and interactions.
`paired-contrasts.csv` contains method differences and the thickness×conductivity
difference of paired differences. These percentile intervals are conditional
simulation summaries with uncalibrated coverage: only two heads/family and three
chosen families exist. They are not human-population confidence intervals or
confirmatory statistical findings. Missing planned cells are incomplete, never
imputed or excluded to improve a mean.

Every one of 44,064 planned reconstructions was computed: 40,392 nonspherical
plus 3672 new spherical controls. There were zero rejected reconstruction
configurations. This does not erase the six failed independent-reference
agreement gates, the earlier geometric design amendment or unsupported comparisons.
No human MRI, EEG, skull segmentation, participant surfaces or phantom recordings
were used. Real geometry, anisotropic conductivity, realistic source priors,
external four-layer solutions and physical phantom validation remain open.

For linear resolution matrices K G, MNE/Tikhonov self-gain has unit 1. dSPM
self-gain has unit 1/(A m), because the input is a unit physical current moment
and the output is normalized. Applying the kernel to actual measured voltages
instead gives dimensionless dSPM source estimates; these are different quantities.
