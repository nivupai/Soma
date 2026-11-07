# MRI geometry and volume methods (Soma 0.7.0)

This subsystem extends Soma's existing metre-valued coordinate contracts. It
provides structural image geometry and numerical modeling, not participant-specific
anatomical validation or a production tissue model. The initial implementation
plan and the recorded surface-convergence refinement are in
[MRI_IMPLEMENTATION_PLAN.md](MRI_IMPLEMENTATION_PLAN.md).

## Volumes and source metadata

`imaging.Volume` contains a real scalar three-dimensional array or lazy proxy,
a voxel-to-world affine, intensity/label kind and provenance. The world convention
is NIfTI RAS+ and the internal physical unit is metres. Shape, stored dtype,
column-norm spacing, origin, orientation, voxel volume, geometry identifier and
voxel-edge physical bounding box are inspectable. A geometry ID identifies a grid,
not a participant or image content. Image identity additionally uses source SHA256.

Construction does not copy or convert voxel arrays. `array()` materializes scaled
values only when requested and preserves their natural dtype; `array(dtype=...)`
is an explicit conversion. Header dtype and effective scaled dtype can differ.
Registration explicitly uses normalized float32 metric images; the standalone
SimpleITK adapter preserves scalar dtype when normalization is off and converts
byte order when necessary. SimpleITK's image construction requires a copy.
Non-real/vector/object images are rejected by this scalar anatomical API.

NIfTI-1 and NIfTI-2 are read through NiBabel. Four-dimensional input requires a
valid explicit frame and uses a frame proxy; the API never silently selects a
functional time point as anatomy. Image dimensionality, affine, units and shape
are validated without full image materialization. For uncompressed .nii, the
header's expected byte count is checked against file length. Full finite-data
validation materializes voxel values; lazy metadata inspection alone cannot
validate compressed pixel payloads or prove anatomical correctness.

Both stored qform/sform matrices, their codes, coded availability, chosen affine,
source units, scaling slope/intercept, pixdim and source checksum are retained.
The default `policy='error'` rejects conflicting coded forms or two uncoded
forms. Explicit `nibabel` selects coded sform before coded qform, falling back
to the NiBabel base affine only when neither is coded. Explicit `qform`/`sform`
requires that form to be coded. Ambiguities generate machine-readable diagnostics
and a warning under an explicit permissive policy; the source header is never
rewritten to hide the discrepancy. Unknown units require `units_override`.
The qform/sform comparison is performed after converting physical values to m.
See [NiBabel's NIfTI semantics](https://nipy.org/nibabel/nifti_images.html).

The stored affine is not silently replaced with a preferred orientation. A
pixdim/selected-affine spacing disagreement is recorded. Spacing outside the
broad supported 0.01–100-mm range is rejected; unusual structural spacing outside
0.1–20 mm is separately flagged. Nonfinite/singular/near-singular affines are
rejected (minimum/maximum singular-value ratio below 1e-8). Unexpected storage
axis codes can be flagged against an explicit expectation, but header orientation
alone cannot diagnose a true anatomical left/right error.

## Index coordinates and physical frames

Voxel coordinates are dimensionless. `geometry.VoxelMap` maps an identified grid
to metre-valued RAS points and solves the inverse map. It permits negative affine
determinants and shear: reflected array storage is distinct from reflecting the
physical subject. Existing `Points` remains metre-valued and rejects the new
VOXEL frame; voxel indices cannot enter the rigid physical-transform API as m.
Physical RAS and LPS frames extend the existing head/MRI/device/template frames.
RAS↔LPS multiplies x and y by −1 and is a proper rigid change of convention.

Physical `Transform` composition/inversion retains the Milestone 6 frame and
proper-rotation checks. Translation applies to points, not vectors. Vectors use
the affine's linear part; normals use its inverse transpose and are normalized.
A generic voxel map is not mislabeled as a rigid head-to-MRI transform.
Tests compare homogeneous coordinates with NiBabel, and SimpleITK physical
index points with the expected RAS/LPS conversion, including a negative storage
axis, anisotropic spacing and a nonzero transformation center.

`reorient` permutes/flips storage and composes the matching inverse orientation
map into the affine. The physical positions and corresponding intensities do
not change; there is no interpolation. This differs from resampling or anatomical
registration. Voxel support bounds use −0.5 and n−0.5, rather than confusing
voxel centers with voxel outer edges.

## Pull resampling

For source voxel map A_s, target/reference map A_r and physical transform
T_reference→source, the pull matrix is

`M_voxel = solve(A_s, T_reference→source @ A_r)`.

Each output index samples the source at `M_voxel @ [i,j,k,1]`. SciPy nearest,
linear and cubic interpolation are supported, with explicit background, output
shape, physical grid, order and direction in provenance. Integer intensity data
are promoted for non-nearest interpolation to avoid silent rounding. Labels and
boolean masks require nearest neighbor; nonnegative labels and representable
integer background values are enforced. Resampling cannot invent intermediate
anatomical label IDs. Cubic interpolation may overshoot and is not appropriate
for discrete anatomy labels.

Identity resampling preserves data within the interpolation's numerical precision;
nearest/linear identity and analytic ramp tests independently verify direction
and offsets. Arbitrary resampling loses information. In-memory lineage rejects
repeat resampling unless `allow_repeated=True`; controlled registration experiments
explicitly acknowledge their second pass. A bare external NIfTI file cannot
reliably reveal earlier interpolation, so this guard is not a universal history
detector. Transform composition followed by one interpolation is preferred.

Derived NIfTIs are written to new paths only, in mm with explicit sform code 2.
NIfTI-1 is the default; an explicit version selects NIfTI-2. Boolean masks are
stored losslessly as uint8 because NiBabel does not support boolean NIfTI storage;
other supported scalar dtypes are explicit, including int64.
For a sheared affine the qform is uncoded, rather than encoding an approximate
rotation and creating misleading metadata. Original raw MRI files are immutable.
Per-operation JSON/NPZ manifests retain richer source/processing history than
NIfTI headers alone can represent.
