# Milestone 11 human MRI integration — frozen addendum protocol

Baseline: 10ead8c, Soma 0.11.0, 612 tests. This is a new addendum, not a rewrite
of historical M11 missing-data reports or their frozen configurations. File-name,
Readme/manifest and header inspection precedes this seal; no new human benchmark
scores have been inspected. All selection/mapping/method choices below are fixed.

## Local references and restrictions

Use the user-provided IBSR v2 skull-stripped NIfTI release, all 18 discovered
subject folders, for pipeline development/descriptive analysis. Previously examined
IBSR header/reference IDs are development metadata. Use the five discovered
MRBrainS training folders for external evaluation with frozen baseline parameters.
Do not open, hash, score or use arrays from the MRBrainS test partition; inventory
its file names/counts only, including unexpectedly present label-named files.
Do not call this an official hidden-test challenge result or universal prospective
validation. Different dataset namespaces prevent numeric subject-ID collisions.

Local MRBrainS Readme matches the 2013 challenge's four modalities, five training
and fifteen test cases, anisotropic registered T1/T1-IR/FLAIR, 1-mm T1, eight-class
training and three-class testing-style labels. MANIFEST.TXT lists three files and
sizes, not a license or proof of portal acceptance. Verify local archives against
those sizes and exact selected member bytes, preserving mismatch diagnostics.
User instruction authorizes local research methods evaluation; no broader use,
commercial permission, redistribution or anonymous-data certification is inferred.
Record local Readme/manifest hashes in ignored reports. Cite Mendrik et al. 2015,
doi:10.1155/2015/813696. IBSR local notice states Rohlfing public-domain release
with citation doi:10.1109/TMI.2011.2163944; retain source conditions and do not
infer that paper licenses grant MRI rights. No data, participant records, source
headers/paths, per-participant tables or images are committed. Keep these only
in ignored reports/data trees. Commit only code, generic policy, aggregate results
and a non-identifying verification summary. No scans or images are uploaded.

## Inventory, geometry and source matching

Discover actual directory contents by recursive role matching, not assumed root
folders. Exact per-subject role names are verified after discovery. Preserve all
alternative/duplicate image entries in inventory. Prefer the single .nii.gz file
for each IBSR role; uncompressed duplicates are not extra subjects. Fail ambiguous
same-role duplicates, identity/path mismatches, absent roles or incompatible labels.
Use IBSR stripped T1 and non-filled segTRI reference; neither anatomical parcellation
nor the CSF-filled derivative replaces reference truth. The original whole-head
T1 is inventoried, not used as if on the same voxel grid.

Validate both coded affine forms, finite nonsingular transforms, shape/zooms,
units, axis orientation, physical corner bounds and source-image/label identity.
IBSR: observed singleton fourth axis may be explicitly selected at frame0; refuse
any genuine multi-frame image without a separate policy. Both chosen inputs have
coded sform, uncoded qform and unknown units. Explicit mm interpretation is
justified by published IBSR v2 voxel spacing (1.5 mm slice; .837/.9375/1 mm in-plane)
and matching local headers; record this override, never change source headers.
Use coded sform in the existing loader; preserve its diagnostics and original forms.
IBSR image/reference grids must match exactly within existing Volume tolerances.

MRBrainS: select aligned T1.nii, never T1_1mm, with LabelsForTraining.nii.
Readme explicitly places reference labels on the aligned multi-contrast grid.
Select coded sform for all image/reference files, retaining qform diagnostics.
Pre-analysis header check found maximum q/s corner disagreement about .4291 mm
and image/reference sform corner difference .01584 mm. Reject q/s corner differences
>.5 mm or image/reference differences >.05 mm, unequal shapes or uncoded units.
When grids differ below that declared tolerance, resample the T1 intensity once,
linearly, to the unchanged native reference grid with identity world transform.
Do not fit registration, move labels, snap affines or choose a transform by scores.
Record original grids, corner displacements and pull affine. Other modalities are
inventoried but not consumed by the baseline; their registration metadata is checked.

## Ontology and independent prediction

Canonical targets: 1 CSF, 2 GM, 3 WM; 0 background. IBSR non-filled segTRI labels
already use this ontology, as the official release describes; reject other codes.
MRBrainS native 1 cortex/2 basal ganglia -> GM, 3 WM/4 WML -> WM, 5 peripheral CSF/
6 ventricles -> CSF. Native 7 cerebellum/8 brainstem form an explicit invalid-domain
mask, not background truth. Preserve native labels and compare mapped three-class
reference to the testing-style labels in the TRAINING directory as an ontology
consistency check only, not as an independent segmentation result. No test labels.

Independent prediction is the existing Soma global T1 multi-Otsu baseline:
256-bin histogram, foreground >2% maximum, three ascending intensity classes
CSF/GM/WM. No trained weights, manual adjustment, reference mask, threshold tuning,
per-subject class permutation, atlas fitting or external-test outcome selection.
Fit thresholds from that subject's image histogram only, on the prespecified input.
IBSR input has supplied upstream skull stripping/bias correction: not independent
of the dataset's preprocessing/annotation lineage and not a Soma skull-stripping
validation. MRBrainS full-head aligned T1 has extracranial confounds; poor results
must remain. No anatomical reference informs threshold fitting or foreground.

## Metrics, uncertainty and failures

Reuse LabelVolume/score with additive explicit valid-domain support. Compute
per-subject/per-tissue Dice, Jaccard, sensitivity/specificity and signed/absolute
volume differences in physical mm³. For MRBrainS count overlap only within valid
voxels and exclude native tissue boundary faces abutting invalid voxels or volume
exterior. Do not create artificial matching surfaces by zeroing excluded voxels.
Area-weighted native voxel-face centers define ASSD/pooled HD95/surface Dice at
1/2mm; if a boundary is unobserved, preserve null distances and explicit diagnostics.
These are finite voxel-surface approximations, not exact subvoxel anatomy. Anisotropic
MRBrainS sampling and limited field of view limit cross-dataset comparability.
Both-absent labels separate; missing predicted classes score zero; retain all
subjects, failures, skipped roles and invalid-geometry diagnostics. No favorable
subject exclusions or silent label resampling.

Report dataset-specific per-subject macro Dice, per-tissue metrics and subject
bootstrap mean/95% percentile interval with 2,000 draws seed11042. Statistical unit
is subject, not voxel, tissue or slice. Report descriptive domain differences with
separate cohort uncertainty, not causal scanner/dataset effects. No multiple-testing
significance or population-wide claims. No human tissue result certifies skull,
scalp, conductor nesting, BEM anatomy or clinical validity.

## Outputs and preservation

Write a new exclusive output root under ignored reports, with actual discovery
inventory, restricted per-subject paths/metadata, source/reference/prediction hashes,
geometry/alignment receipts, numerical tables, prediction NIfTIs, NPZ arrays, figures,
software/Git/source identity, wall/CPU and peak RSS with bounded workers1. Inspect
all result summaries and sampled native overlays. Pin the selected file content
in the first inventory; freeze its SHA before external scoring and reject changes
between development and external evaluation. Existing reports/seals and 612 tests
must remain unchanged. Add numerical/adversarial and opt-in dataset tests. Run
pytest/Ruff/format/strict mypy/pip check. Commit local implementation with requested
message, never raw data or participant information. No push, no Milestone12.
