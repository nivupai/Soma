# Milestone 11 prospective protocol

Baseline: Soma 0.10.0, commit 0a4761d, 541 tests. This protocol and five
configuration files are sealed before new reference scoring or holdout inspection.
Metadata discovery precedes the seal. Earlier BrainWeb normal and Mindboggle
NKI-RS-22-11 are development evidence, never new holdouts.

## Reference selection and access

Primary external model: University of Utah SCI Head Model, Warner et al. 2019,
doi:10.1101/552190, official https://sci.utah.edu/sci-head-model/ . The site
lists one female participant, bias-corrected T1/T2 NRRD, Seg3D eight-layer labels
and Cleaver tetrahedral FEM. Institution requests attribution and NIH grant
acknowledgment. Verify actual archive contents, header units/frame and label
ontology before use. Inspect documentation for manual/expert/automatic/derived
status; unknown evidence stays unknown. No assumption of anatomical truth.
Do not fetch multi-million-element FEM meshes merely to certify unrelated BEM.
Retain archive identity/checksums and diagnostic missing/unsupported statuses.

MRBrainS13 is local-authorized-only: no account creation, terms circumvention or
hidden test labels. None is initially present. Documented substitute: IBSR v2.0
skull-stripped NIfTI distribution, NITRC release 2316 (2013-07-11), CMA/MGH expert
manually guided tissue references. Record original notice, citation and use
conditions; local research in segmentation automation only, no raw redistribution.
Select IBSR_01 development, IBSR_02/03/04 prospective holdout, regardless of scores.
Download transport may contain other subjects: extract only selected subjects and
document transport size. Verify 0/background,1/CSF,2/GM,3/WM against README before
scoring. Never remap cortical parcellation into skull/scalp truth. No site access
means explicit blocked criterion, not fabricated reference substitutes.

## Cohort, ontology and independence

Use existing Volume/LabelVolume; preserve native source identity, modality T1,
scanner/protocol metadata when documented (unknown otherwise), affine/frame/units,
reference version/provenance, split and backend provenance. No implicit alignment
or registration. Reject mismatched subjects, ontologies, spaces and grids; explicitly
justified nearest-neighbor resampling must have a transform receipt. Reference and
prediction cannot share path/hash, derivation or array. Simple baseline: existing
three-class global multi-Otsu with foreground >2% maximum, ordered CSF/GM/WM,
on supplied skull-stripped T1 with no reference-derived ROI. Its foreground depends
on supplied preprocessing, not Soma skull stripping. Freeze parameters; do not tune
on holdouts. External outputs require tool/version/model, ontology mapping,
transform history, modality, options, runtime and failures. Supplied references
are not automatically error-free; no independent inter-rater uncertainty available.

Primary outcomes: subject-level macro tissue Dice and per-tissue Dice, ASSD, HD95,
surface Dice 1/2 mm; secondary sensitivity/specificity, volume, component and mask
surface diagnostics. Use M10 exposed voxel-face physical area-weighted surfels,
not continuous exact boundaries. Missing prediction label scores zero; both absent
separate. All subjects, failures and missingness retained; no score-based exclusions.
Subject bootstrap percentile intervals (2,000 draws) summarize this selected small
cohort, not population certification. No voxel/label pseudoreplication. Report paired
subject differences if multiple compatible methods exist. Scanner subgroup analysis
only with documented fields and >=2 subjects/group; otherwise unsupported.

## Conductor policy

Keep tissue/cortex boundary accuracy distinct from skull/scalp boundary accuracy
and computational mesh validity. SCI FEM materials cannot certify three-layer BEM.
Verify NRRD geometry, connectivity, masks and interfaces; diagnostic resampling
is explicitly separate from native reference segmentation. Preserve PASS/FAIL/
INDETERMINATE semantics via existing ConductorSurfaces machinery. Unknown interface
correspondence, conductivity, electrode mapping or validation prevents anatomical
PASS. Do not aggregate eight tissues into three shells without an explicit model.
Actual usable external surfaces are evaluated; unsupported FEM conversion is not
performed. Synthetic known nested spheres are the validated numerical control:
80/85/90 mm boundaries, scalp/skull/brain .3/.006/.3 S/m. Perturb brain radius +1 mm
or skull conductivity half; recompute MNE forwards, preserving sensors/source order.
No assertion that synthetic perturbations represent biological variability.

## Priors and inverses

Use M10 continuous MRI dipoles, positions, moments, 0/30 degree orientations and
20/15/10 mm grids (non-nested), 24 EEG, average reference. Offgrid tolerance .5 mm,
independent truth evaluation, no interpolation of reconstruction columns. Distinguish
same-grid controls, shared-conductor offgrid, BEM discretization mismatch and
boundary/conductivity mismatch. Shared isotropic spherical physics is declared.
Uniform per-component variance; depth factor based on lead-block Frobenius norm,
exponent .8 with 10-fold cap; area factor based on declared quadrature measure;
orientation covariance nnT+.2(I-nnT); combined depth*area. Area units m² explicit;
no claim volumetric points have anatomical cortical patches. For volumetric sweep,
4*pi*(.065m)^2/N is an equal quadrature weight, a controlled numerical convention.
Provide actual mesh vertex dual areas for surface applications with independent tests.
Prior coefficients describe dipole moments in A m; separate density interpretation
Q_moment=A Q_density A, versus independent density-white-noise measure Q proportional
A. Do not conflate these stochastic models.

Sensor-trace normalization Q' = Q / tr(W L Q L^T W^T), target 1 dimensionless
whitened sensor covariance unit. Unnormalized policies kept. Fixed physical ridge
alpha=lambda2*baseline20mmuniform_trace/rank for each representation/noise model,
held across priors/grids; lambda2=.01,1/9,1. Prior construction uses no evaluation
truth. Inverse K=Q Lw^T(Lw Q Lw^T+alpha I)^-1 W; source-space PSD and rank explicit.
No dense source-by-source matrices: diagonal or 3x3 blocks; selected resolution columns,
trace(KL) via sensor trace. Independently test diagonal/low-rank/scaling/basis laws.
MNE numerical agreement must declare trace/rank normalization equivalence, depth=0
for exact uniform covariance comparison; do not imply arbitrary area priors match
MNE depth .8 internals.

## Experiments and uncertainty

Prespecified full source-priors sweep: fixed/free; five priors; normalized/raw;
three grids; three ridges; single source superficial/deep and normal/oblique;
20 matched projected Gaussian draws at SNR10 plus noise-free outcomes. Signals
10 Hz sampled100 Hz over1 s. Additional correlated pair corr .8, matched versus
diagonal fitted noise covariance, and distinct BEM/boundary/conductivity forwards
at lambda2=1/9. Grid-priors is reduced single-source shared-conductor analysis
retaining all three grids/priors/ridges. Explicitly label reused conditions.
Primary contrast normalized-minus-raw uniform peak error and amplitude; all other
comparisons exploratory sensitivity, no best-prior selection. Paired Monte Carlo
mean differences and 95% t intervals concern the sampled noise at fixed sources,
not human subjects. No inferential ranking or uncorrected multiple-comparison
significance claims. Preserve interaction differences and failures.

Record peak error, nearest-grid bound, dispersion, nearest moment attenuation,
sensor residual, noise amplification, prior trace, sensor covariance trace,
resolution diagonal gain, effective model complexity, singular spectrum, source
order and forward fingerprints. Correlated sources report nearest-source coverage
and common-sensor residual without pretending isolated source attribution.
Finite/nonfinite checks, unsupported zeros and failure counts explicit.

## Outputs and acceptance

All six CLI actions must perform real work or report structured missing/unsupported
evidence. Default CI offline; real datasets/MNE integration opt-in. Bounded workers1;
record environment, stage wall/CPU and process RSS, dimensions, code/input/output
hashes and cache provenance. Retain old541 tests and report hashes unchanged.
Generate evidence-labeled overlays, subject/tissue metrics, mesh diagnostics,
lead perturbation/prior/depth/grid/gain/cost figures with arrays. Freeze before
holdout inspection; never rewrite seal after results. Record incomplete actual
external conductor/tissue criteria rather than claiming synthetic certification.
Target .11.0, local requested commit, no push and no Milestone12 implementation.
