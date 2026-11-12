# Frozen source uncertainty experiment, v0.26.0

This is a controlled numerical experiment on an idealized synthetic head, not
human source localization or validation of a participant's anatomy. The complete
prespecified design is `src/soma/resources/source-uncertainty-v26.json`. Its byte
hash and Git commit record the freeze before final scientific outcomes. The M19
seal binds this design; execution rejects drift. Local sealing is not external
preregistration. No outcome-dependent regularization, exclusions or model selection.

MNE's conductivity-aware four-shell sphere uses brain/CSF/skull/scalp outer radii
81/82.8/87.3/90 mm and conductivities 0.33/1/0.004/0.33 S/m. These reproduce the
[MNE sphere defaults](https://mne.tools/stable/generated/mne.make_sphere_model.html)
at a 90 mm scalp radius. MNE uses the fitted equivalent-source approximation
([implementation](https://mne.tools/stable/documentation/implementation.html));
its fit residual is not a PDE solver residual or independent FEM validation.
Skull values 0.002–0.02 S/m are a sensitivity range, not an inferred population
prior. Values in this range have been investigated in
[Unnwongse et al., 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9942548/).
That paper's human results are not Soma results.

The 32 synthetic electrodes cover a cap on a sphere. There are 48 free-orientation
inverse candidate locations on two shells and 12 independently seeded off-grid
truth locations/orientations in the upper hemisphere. Truth forward fields are
computed separately, never by an inverse kernel. Measurements are fixed across
estimated-model perturbations. Zero noise has one realization; each of two fixed
sensor-noise standard deviations has eight independent projected Gaussian draws.
This is 204 generated measurement vectors per configuration, reused in paired
comparisons; source/noise vectors reused across models are not independent heads.

Experiments perturb the inner/outer skull boundaries by up to 1/2 mm, conductivity,
electrode RMS displacement up to 10 mm (three fixed patterns), head-to-MRI x
translation up to ±10 mm and z rotation up to ±10 degrees. Whole boundaries shift
radially: these are smooth geometric segmentation surrogates, not realistic local
lesions or measured segmentation error distributions. A 2^4 factorial combines
outer-skull displacement, conductivity, electrode displacement and translation.
All planned failures remain in the tables. The physical head and truth never move.

Existing Soma Tikhonov, MNE and dSPM operators use fixed parameters. Tikhonov uses
a single baseline lead-field spectral scale and lambda2=0.001. MNE/dSPM use
lambda2=1/9, no depth prior and free Cartesian orientation; their normalizations
are the fixed method's algorithm, not fitted to perturbation outcomes. dSPM is
dimensionless: it has no physical amplitude-bias estimate. Peak distance and
energy-weighted spatial spread are measured in true MRI millimetres; grid
quantization and the nearest possible candidate error are recorded. Euclidean
spread is not cortical geodesic distance. Per-source Monte Carlo means are
bootstrapped across the 12 independent generator draws, retaining paired noise
structure. These conditional intervals are not human population confidence.

Numerical controls compare the SVD inverse with an independent linear solve,
check MNE kernel versus direct application, inspect reference nullity/rank and
sphere approximation residuals, halve finite-difference steps and double inverse
grid density without choosing a preferred grid from outcomes. Resolution uses
both the matched operator K G_estimated and the mismatched response K G_truth.
Neither operator is a physical anatomical ground-truth certificate.

No MRI/EEG or model weights are acquired or redistributed. Historical IBSR tissue
scores, including poor CSF performance, do not certify skull/scalp BEM surfaces.
MRBrainS remains unavailable for this study. Public artifacts are generated
synthetic tables, vector figures and reviewed numerical summaries only.
