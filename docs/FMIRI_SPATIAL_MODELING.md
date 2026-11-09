# Functional spatial modeling

Voxel shape is not anatomical space. SpatialMap binds a Soma Volume, subject,
space identity, quantity and provenance. A native image and an MNI atlas require
an explicit validated transform even if array dimensions happen to match.
SpatialChain records subject, reference-space/source-space identities, evidence
and the existing RAS-metre Transform mapping reference physical points to source.
No arbitrary nonlinear warp is accepted as an affine. Existing Transform inversion
and composition remain authoritative. Native world geometry survives export.

Discrete ROIs require explicit atlas/source and label mapping. Different grids or
spaces require the identified pull chain; labels use nearest-neighbor resampling,
never continuous interpolation. Unknown labels fail. Coverage, absent regions,
physical volume (abs affine determinant), mean effects and partial-volume warnings
are reported. A transformed label region is not a newly certified anatomical truth.
No MNI atlas is applied directly to raw SPM native BOLD. Its primary ROI is the
prespecified whole EPI intensity foreground, a heuristic analysis domain rather
than an anatomically validated auditory cortex mask.

Volume-to-surface/point sampling uses physical Points in RAS metres and trilinear
interpolation after VoxelMap inversion. Subject/space and field-of-view checks
precede sampling. Hemisphere checks additionally require a validated x=0 midline;
a scanner origin alone cannot establish hemisphere. Source-to-ROI aggregation
uses nearest discrete voxel membership, preserving missing-source coverage.
Source values must align to coordinate counts; existing SourceCoordinates.points
can supply source geometry. EEG source amplitudes/power and fMRI effect units remain
distinct. No point localization is treated as exact anatomical ground truth.

Surface-to-volume projection here is explicit nearest-voxel scatter/averaging
with a separate contribution-count volume. It is sparse, many-to-one and not an
inverse of trilinear sampling; uncovered voxels are zero only with the count mask.
It is not cortical ribbon reconstruction. Synthetic linear-field tests have
independent interpolation oracles; synthetic translation/smoothing/source-mixing
examples isolate known perturbations. These do not decompose errors in real data.

Retest requires same subject/task/contrast/space, different recorded sessions,
matching grids and explicit shared cross-session alignment evidence. Metrics use
the mask intersection and include map correlation, FDR overlap, ROI means/change,
voxel RMSE and two-session sample variance. Empty/empty activation Dice is undefined.
No two-map population ICC or separation of registration/estimation/physiology is
claimed. Native grids agreeing numerically do not substitute for alignment evidence.
