# MRI geometry and anatomical limits

Soma Volume stores a three-dimensional array and `affine_m`. For a voxel-center
index column v, RAS+ metres are `x = affine_m @ [v, 1]`; inverse mapping solves that
affine. Indices can be fractional. Storage orientation (RAS/LAS/etc.) does not
change the world convention and cannot by itself diagnose an anatomical left/right
error. Voxel corners lie at -0.5 and shape-0.5. Voxel volume is abs(det(A[:3,:3])).

NIfTI stored mm/micron units are explicitly converted to metres. Coded qform and
sform are validated; disagreement requires an explicit policy. A 4D input requires
an explicit selected frame. Unknown units require an explicit override that is
recorded. Metadata inspection is lazy; request `check_data=True` to check finiteness.
A matching array shape is insufficient to establish physical alignment or subject
identity. `require_same_space` requires explicit metadata and matching affine/grid.

RAS→LPS flips x and y, preserving z. Points/Transform reject implicit millimetres
and mismatched frames. SimpleITK conversion uses the existing RAS/LPS adapter.
Registration returns a reference-to-source pull mapping, not a source push map.
Nearest-neighbor interpolation is mandatory for labels; intensity orders 1 and 3
are available. Repeated resampling changes images and needs explicit opt-in.

Segmentation scoring requires identified LabelVolumes with matching ontology,
subject, space and grid. Zero means background. The SDK rejects undeclared IDs.
Dice=2TP/(2TP+FP+FN); Jaccard=TP/(TP+FP+FN). Both absent is undefined (None), not a
perfect segmentation. Physical boundaries are exposed voxel-face centers with
parallelogram areas, in mm/mm². ASSD weights both directions by area; HD95 is the
pooled area-weighted empirical percentile. These are discrete representations,
not exact continuous tissue boundaries. Signed volume error is prediction minus
reference in mm³. Observation masks censor boundary faces as documented in output.

Meshes store physical metre vertices and oriented integer triangles. Area is m²;
signed enclosed volume is m³ and orientation dependent. Valid volume requires the
existing topology/intersection checks; output explicitly marks unreliable volume.
These checks do not establish tissue identity, adequate scalp/skull segmentation,
BEM conductor validity or participant coregistration. Synthetic sphere/tetrahedron
results validate numerical conventions only. Human tissue metrics cannot validate
skull/scalp conductor anatomy, conductivity, cortical localization or clinical use.

Run `python -m examples.mri_geometry`, `examples.segmentation` and
`examples.surface_qc` from the repository root, using `python -m` for each module.
