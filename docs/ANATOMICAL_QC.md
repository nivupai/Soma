# Anatomical processing QC and evidence

Ingestion preserves original qform/sform, units, spacing, axis codes and physical
field of view. Existing Volume/VoxelMap tests enforce nonsingular physical geometry
and voxel/world roundtrip. Default raw BIDS loading rejects ambiguous forms or
uncoded units. Explicit qform/sform selection is recorded. Legacy adapters retain
the documented IBSR singleton/mm convention and MRBrainS registered-grid policy.

Intensity QC rejects nonfinite/constant/nonpositive images, reports native scale,
positive-foreground quantiles and histograms, and never silently z-scores data.
N4 correction is opt-in: SimpleITK RAS/LPS bridge, positive-support mask, bounded
iterations/shrink and one thread. Record requested/final iterations, final level,
convergence measure/threshold, before/after geometry and time. Orthogonal grids are
required by the existing SITK bridge; shear is rejected rather than silently fixed.
No convergence value establishes biological correctness or better segmentation.

Masks must have nonempty, non-full binary support, matched subject/input MRI
fingerprint and matching physical grid. Threshold masks remain heuristic ROI
candidates. Mask application to segmentation is a separate explicit option.
Backend outputs must declare tool/version/model/contrast/ontology/mapping/runtime/
warnings and compatible identity/geometry; unknown labels fail. Region volumes
and missing tissues are reported, but plausible-looking totals do not certify
anatomy. Imported annotations cannot be used as independent reference predictions.

Requested surfaces use existing marching cubes and topology/QC. No automatic
smoothing or repair is introduced. Missing/clipped surfaces fail extraction;
unrequested surfaces remain unsupported. Intersection checks are bounded by the
face limit and explicitly unassessed above it. Genus is never promoted for invalid,
nonorientable, disconnected or unchecked meshes. Mesh numerical validity and tissue
annotation compatibility do not establish skull/scalp interfaces or conductivities.

Numerical invariants may PASS/FAIL; mask/label anatomical plausibility and overall
anatomical/clinical/BEM readiness remain INDETERMINATE without independent evidence.
Reference benchmarking is a separate operation with manual-label uncertainty,
valid-domain exclusions, subject-level uncertainty and no self-comparison.
Previously examined MRBrainS training cases are not fresh external holdouts.
Figures and their arrays are optional private reports: native/output affines,
preprocessing and overlays, histograms, stage time/cache, DAG, volumes and surface
status. Clinical diagnoses or automatic anatomical certification are not produced.
