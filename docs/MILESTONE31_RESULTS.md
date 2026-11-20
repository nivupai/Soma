# Milestone 31 results: inverse priors and regularization

Design SHA256: `abb24125e39c51438197e4e7301b3f7079bdb4820bdd6257069348594d6468bc`.
Pre-evaluation protocol commit: `44adeed`. The six synthetic heads are unchanged;
72 original source draws are retained, with 24 new independent seeds. There are
36 calibration sources and 60 test sources (36 original + 24 new). No added heads
or human participants are claimed. The new source draws include locations and
orientations; final locations never enter candidate grids or tuning rules.

## Historical M30 replication

Original physical fields, noise stream, eight noisy repeats and unchanged inverse
settings reproduce the four required rows. The independent inverse implementation
agrees with historical SVD/MNE kernels to relative 1.652×10⁻¹³. The table is all
72 original sources at 0.05 µV; it is separate from the new test estimand.

| candidates | method | nearest_mm | localization_mm |
| --- | --- | --- | --- |
| 12 | MNE | 53.441 | 56.031 |
| 12 | Tikhonov | 53.441 | 55.506 |
| 12 | dSPM | 53.441 | 56.569 |
| 33 | MNE | 14.831 | 24.536 |
| 33 | Tikhonov | 14.831 | 24.347 |
| 33 | dSPM | 14.831 | 46.290 |
| 147 | MNE | 9.814 | 26.587 |
| 147 | Tikhonov | 9.814 | 32.934 |
| 147 | dSPM | 9.814 | 43.048 |
| 341 | MNE | 7.479 | 26.985 |
| 341 | Tikhonov | 7.479 | 34.613 |
| 341 | dSPM | 7.479 | 42.046 |

## Held-out paired experiment

99,360 reconstruction rows comprise 90,720 primary FEM rows and 8,640 BEM-subset
rows. All 3,726 planned inverse configurations computed; numerical failures: zero.
No configuration was removed or replaced to improve an outcome. The six fresh
finest-mesh FEM truth operators for 24 new sources are public. Candidate operators
are hash-verified M30 fields, with union-grid columns mapped by exact coordinates.
Finest truth versus level-2 candidates avoids exact operator reuse, while shared
FEM assembly and synthetic heads retain correlated-validation limitations.

Cell-volume, nested-481, 0.05 µV results below average 60 test sources after averaging
noise draws. Conditional intervals resample paired heads within the three fixed
families and sources within heads (999 draws). They do not provide calibrated
human-population coverage.

| method | policy | localization_mm | localization_mm_lower | localization_mm_upper | excess_mm |
| --- | --- | --- | --- | --- | --- |
| MNE | historical | 23.223 | 19.191 | 27.654 | 16.174 |
| MNE | prediction | 23.174 | 18.949 | 27.951 | 16.125 |
| MNE | spectral | 24.950 | 21.147 | 29.133 | 17.901 |
| Tikhonov | historical | 24.513 | 19.968 | 29.730 | 17.464 |
| Tikhonov | prediction | 23.174 | 18.949 | 27.951 | 16.125 |
| Tikhonov | spectral | 24.564 | 19.969 | 29.911 | 17.516 |
| dSPM | historical | 41.345 | 39.337 | 43.347 | 34.296 |
| dSPM | prediction | 42.488 | 40.342 | 44.527 | 35.439 |
| dSPM | spectral | 34.778 | 32.650 | 36.901 | 27.729 |

Under historical regularization at this grid/noise, the paired cell-volume minus
unweighted error is −12.815 mm [−18.249, −7.657] for Tikhonov; −3.236 mm
[−5.962, −0.603] for MNE; and +0.152 mm [0.000, 0.454] for dSPM. This is a
prespecified paired comparison, not a best-performing configuration chosen after
test outcomes. The separate 24-new-source sensitivity is in `new-heldout-only.csv`.

H1 is supported in this design: fixed historical unweighted Tikhonov parameters
produce changing prior power and α/bmax. H2 supports the prespecified fixed-total-
variance property and substantially more stable sensor covariance; it does not
establish universally improved localization or monotonicity. H3 has measurable
paired prior/regularization effects, but no unique causal fraction of the original
nonmonotonicity can be assigned: geometry, spectrum and nonlinear peak selection
interact. H4 is supported descriptively: method/noise/source dependence includes
negative dSPM findings. Formal population hypothesis tests are not claimed.

The two-head (0 and 5) BEM subset uses Cartesian-147 and nested-481, matched source
measurements and all priors/policies/methods. Mean absolute paired peak difference
is 0.865 mm across repeats/conditions. This is a descriptive two-head sensitivity,
not six-head uncertainty or absolute nonspherical validation. No independent new
head, MRI geometry, physical phantom or human EEG validates this inverse study.

All noiseless tuning cases hit the frozen sweep boundary; noisy boundary fractions
are 11.59% and 2.90%. No sweep was extended after seeing outcomes. Physical amplitude
is restricted to integrated moments for Tikhonov/MNE; dSPM amplitudes remain
explicitly dimensionless. PSF width and spatial dispersion do not uniformly improve
with density. Finer geometric nearest distance is insufficient evidence of better
inverse reliability.

## Resources, figures and audit

The initial executed study took 33.372 seconds with process peak RSS 775.406 MiB,
including imports, six fresh truth solves and incremental table writes. Reused
public candidate fields avoid rerunning the full M30 meshing study. Operator times
and cumulative process RSS are separately labeled; the latter is not isolated
per-kernel allocation. The four-hour protocol budget was not approached.

Twelve SVG figures under `experiments/milestone31/figures/` cover baseline replication,
nesting, volumes, covariance, regularization curves, localization, excess error,
PSF, new held-out sources, noise/depth, prior/method interactions and runtime/memory.
Every figure is generated by `scripts/summarize_inverse_calibration.py` from saved
CSV/JSON tables. Actual source-level reconstructions are lossless bounded CSV
shards by head and eight-source block. No medical or participant data are present.
The Explorer reads fingerprint-checked frozen results; its spatial/depth detail
slice is explicitly labeled and never fabricated for unavailable combinations.

The M30 merge is `4e55256f8dcbcb9a104e4b7b16ad495cdabc9191`. Post-merge run
44626578312 has canonical PASS and a changed native failure signature, BLOCK_RELEASE.
The original policy is unchanged. Changed entries are retained in
`baseline-release-blocker.json`: macOS/Linux Python3.11 contrasts fail 10 entries,
macOS/Linux Python3.12 fail 15, Linux3.11/Linux3.12 fail 16. This was already present
before M31 and is not relabeled as the original accepted signature. M31 release
and merge remain blocked while this mandatory review condition is unresolved.

The framework is mathematically defensible for controlled MRI-derived experiments
planned for M32, under its explicit white-density/discretization/whitening assumptions.
It does not establish human anatomical accuracy, optimal physiological priors,
calibrated uncertainty coverage or deterministic native meshing. M32 is not started.

Analysis clarification: the first depth visualization used radial coordinate as an
explicitly labeled proxy. During final review it was replaced with the prespecified
source-depth metric: minimum distance to the finest synthetic brain-interface
triangulation (13.646–46.581 mm). Radius remains separate (35.088–64.558 mm). This
changes no inverse, tuning, split, reconstruction or paired localization result.
The derived distances and all inverse rows are retained in the public tables.
Source generators retain the original upper-hemisphere convention, limiting spatial
generalization. Arbitrary MRI-domain quadrature and physiological source correlations
remain work for subsequent modeling; the current SDK control assumes a 65 mm ball.
