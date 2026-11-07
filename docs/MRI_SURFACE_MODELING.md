# MRI masks, surfaces and geometric readiness

## Labels and masks

Integer/boolean label volumes preserve physical grids and label identities.
Mask/image and segmentation comparisons require matching shapes and affines,
not shapes alone. Binary closing, hole filling, largest-component selection and
6-connected component analysis are explicit operations. Morphology records
parameters and changed voxel counts; iteration counts refer to voxel-neighborhood
steps, not an implicit isotropic physical radius on anisotropic images.
Region volumes use `abs(det(voxel_to_world_linear))`, including shear, rather
than incorrectly multiplying only column norms. Dice and Jaccard have explicit
empty/empty convention 1 and return scalar label-wise overlap. No registration
or resampling is silently performed to make masks match.

The synthetic level phantom has known integer regions and a simple threshold
baseline. Its Dice/Jaccard measure recovery of those synthetic levels only.
Real MRI uses Otsu thresholding followed by explicitly recorded morphology and
coarse resampling to obtain a foreground/head envelope. There is no supplied
manual segmentation and no invented reference Dice score. This procedure is
not validated brain extraction or GM/WM/CSF segmentation.

## Surface extraction and smoothing

Established [scikit-image marching cubes](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes)
extracts a 0.5 isosurface from an integer label mask. Indices are mapped through
the full voxel affine into RAS metres; spacing-only multiplication would lose
origin, orientation and shear. Masks touching the image boundary are rejected
rather than presenting clipped/open geometry as a closed anatomical boundary.
A scalar isosurface API additionally supports analytic continuous fields.

Meshes carry physical points, integer triangle connectivity, frame, units,
source volume metadata and extraction method. Total signed volume determines
global winding after extraction, including reflected storage affines. A positive
total signed volume alone does not establish local winding consistency or validity;
subsequent topology and intersection checks remain necessary.

Optional bounded Laplacian smoothing records iterations, step, maximum vertex
movement, area and signed-volume change and Euler characteristics before/after.
It preserves connectivity but can shrink/distort geometry. The real demonstration
does not use smoothing or hidden repair to turn an invalid mesh into a favorable
result. Revalidate any smoothed geometry before considering conductor use.

## Mesh validity and geometric measurements

Validation measures vertex/face/edge counts, zero-area triangles, duplicate faces,
boundary/nonmanifold edges, nonmanifold vertex links, connected components,
Euler characteristic, directed-edge winding consistency, surface area, signed
volume and dimensionless triangle quality `4√3 area / sum(edge²)`.
A closed connected oriented sphere should have Euler characteristic 2. The
independent tetrahedron tests use exact area, volume and edge counts; pathological
meshes test open, duplicate, degenerate, inconsistently wound and nonmanifold
cases, including two fans sharing only a vertex.

Nonadjacent self-intersection checks use a conservative centroid/bounding-sphere
broad phase and triangle feature distances. Exact feature calculations include
vertex-to-face, segment-to-segment and edge-piercing-face cases; coplanar edge
contacts are included. The broad phase cannot discard a pair closer than its
current upper distance bound. Default touching/intersection tolerance is 1e-8 m.
Adjacent triangles sharing a vertex are excluded from this intersection check;
edge winding, degeneracy and vertex-link topology are checked separately. These
checks are not a general certified solid-geometry kernel or proof against every
adjacent-face overlap pathology. Their scope is explicit in each quality report.

A reliable-under-checks enclosed volume is reported only for a single connected,
closed, consistently wound, positive-volume mesh that passes these checks. A
formal signed triangle sum is retained as a diagnostic, but `enclosed_volume_m3`
is null for invalid, open, inward or unchecked geometry. Skipping expensive
self-intersection validation does not silently grant a reliable-volume claim.

## Nested candidate boundaries

`nested_boundaries` accepts ordered inner/outer/scalp candidates in one physical
frame. Each must pass mesh validation. Cross-surface triangle separation is
computed using feature geometry, not nearest-vertex distance mislabeled as exact
surface clearance. Generalized winding numbers from solid angles classify
extremal probes. For closed connected nonintersecting boundaries, containment of
an inner-boundary point establishes nesting; extrema provide extra diagnostics.
Points on a surface have ambiguous winding classification, so positive separation
and explicit tolerance are required. The default required clearance is 1 mm.

Adjacent containment implies transitive nesting of all three boundaries. Any
intersection/contact or insufficient gap rejects geometric candidacy. Passing
geometry does not validate anatomical labels, skull thickness, conductivity,
segmentation accuracy or sensor-to-head alignment. Reports always retain
`physiological_conductor_validated=false` until independent scientific evidence
exists. The synthetic shells pass; the real coarse MRI foreground surface does
not even pass mesh topology and is explicitly not a BEM boundary.

## Surface convergence finding

Binary sphere masks exhibit roughly 8% area bias across the tested 4/3/2-mm
resolutions, with nonmonotonic errors. More voxels alone do not justify claiming
unbiased anatomy. The original convergence expectation is retained as a failed
binary-mask result. The added continuous signed-distance sphere control isolates
interpolation geometry: its area and volume errors decrease as resolution improves.
The control was added after observing binary-mask bias; it is not described as
an originally predeclared favorable result. Ellipsoid volume is compared with
its exact formula; an approximate ellipsoid area formula is not used as exact truth.
