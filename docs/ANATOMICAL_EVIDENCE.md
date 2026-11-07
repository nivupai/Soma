# Anatomical evidence without certification

Evidence records have a property, explicit check definition, provenance, category
and PASS/FAIL/INDETERMINATE state. Categories distinguish computational checks,
external provenance/reference support, heuristics, missing evidence and failures.
There is no aggregate numerical quality score. External-reference PASS for MRI
origin or FLASH asset attribution supports that narrowly defined provenance
check; it does **not** assert externally validated anatomical tissue boundaries.
No independent validated skull/scalp or MRI-fiducial truth is available.

The assessment records MRI geometry/provenance, segmentation origin, FLASH
surface source, frame/transform chain, topology, nesting, self-intersections,
mesh orientation, sensor compatibility, numerical mesh quality, surface-to-volume
consistency and unassessed anatomical plausibility. Three ico3 solver boundaries
remain computationally acceptable. Subject/frame contracts forbid unrelated MRI,
template substitution and unjustified scanner-RAS/surface-RAS identities.

## Derivative comparisons

Available `brainmask.mgz` and `seghead.mgz` are supplied same-pipeline derivatives.
Their positive-valued voxel support is a foreground proxy; it is not a newly
validated tissue segmentation or independent ground truth. The provided aseg
label/count inventory and checksum are also recorded without inventing tissue
truth. Each derivative's own MGH voxel→surface-RAS map is converted mm→m.

The bounded generic checker measures each surface vertex to the nearest foreground
boundary voxel center using a KDTree, records its signed inside/outside convention,
counts 6-connected mask components, and tests containment of 20,000 deterministic
foreground voxel centers by the triangulated surface. This is not continuous
boundary ground truth; voxel discretization and deterministic sample definitions
are saved. No Dice score is computed. No dense all-pairs distance allocation is
needed. Synthetic analytic sphere masks verify displacement within voxel-scale
accuracy, known outward normals and connectivity.

For sample, median inner-skull→brainmask-boundary discrepancy is 2.025 mm, maximum
10.798 mm. Only 85.815% of sampled brainmask foreground centers lie within the
inner-skull surface; positive-value support has 248 connected components. These
are unfavorable derivative-consistency observations and may reflect derivative
semantics, anatomy or boundary disagreement; they are not hidden or diagnosed as
segmentation errors without reference truth. Scalp→seghead median discrepancy is
1.383 mm, maximum 6.966 mm, and sampled containment is 97.21%. Its support is one
component. Inner-to-outer vertex/triangle separation distributions complement the
M8 exact minimum-gap/intersection checks; they are geometric separation, not
histological skull-thickness measurements.

Overall anatomy remains **INDETERMINATE**. A computational PASS cannot replace
unavailable independent landmark/tissue validation. No clinical validity is
established. The unrelated SPM auditory foreground remains rejected for BEM.
Future validated segmentation backends must supply participant identity, physical
frames, label definitions, generation/version provenance, independent performance
evidence and uncertainty. Merely supplying a foreground mask is insufficient.
