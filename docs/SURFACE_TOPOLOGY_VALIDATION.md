# Topology, reconstruction and conservative repair

The new benchmark layer reuses existing Mesh/Volume extraction and exact triangle
geometry checks. `adjacency` adds edge incidence, face and vertex neighbors,
face-component decomposition, boundary loops and orientation constraints. A BFS
solves neighboring-face orientation signs; inconsistent cycles identify
nonorientability. Branched boundaries are reported rather than treated as loops.

Euler characteristic uses vertices actually referenced by faces. Genus
(2−χ)/2 is reported only for a connected closed consistently oriented manifold
with supported valid geometry and self-intersection assessment. Invalid meshes,
nonorientable strips, open boundaries and unassessed geometry receive no genus.
Independent tetrahedron (χ=2,g=0), torus (χ=0,g=1) and Möbius-strip negative controls
verify formulas and eligibility. No genus formula is applied outside its assumptions.

Surface studies cover analytic sphere, rotated ellipsoid, asymmetric radial shape
and each of three nested spherical boundaries. Binary-mask marching cubes and
scalar-field isosurfaces are separate. Full intersection checks are capped at
20,000 faces: ten finest cases therefore remain unassessed for that condition,
with genus/enclosed-volume certification withheld. Algebraic signed-volume
convergence is labeled separately from validated enclosed volume. The synthetic
BEM shell triples used in forward experiments undergo the existing nesting and
geometry checks; mathematical validity is not human anatomical validity.

## Repair policy and outcomes

Repair consolidates exact duplicate vertices, removes duplicate/degenerate faces,
corrects face orientation and proposes only small triangular hole caps. It uses
no smoothing, learned anatomy or global topology alteration. Limits are perimeter
20 mm, cap area 20 mm², vertex displacement 0.25 mm and relative area change 1%.
Every audit retains before/candidate topology, components, area and valid-volume
changes, operations, displacement and acceptance/rejection reason. Rejected
operations return the original object. Undefined pre-repair enclosed volume stays
undefined; it is not used to invent a volume-preservation claim.

Of eight known-sphere cases, the valid control remains valid; duplicate vertex,
duplicate face, degenerate face, small triangular hole and mixed orientation
fixtures are computationally repaired. Large unsupported holes and genuine
self-intersections are rejected. Accepted fixtures have zero vertex displacement;
the small cap changes area by approximately 0.073%. A new cap still requires
anatomical review. The API operates on geometry and does not rewrite reference
labels or establish per-vertex attribute remapping for an annotated human surface.
A watertight repaired object is never called anatomically validated.

Controlled mask experiments independently include 1-mm dilation/erosion/radial
shift, a local removed box, disconnected island, seeded 1-mm boundary-field noise,
eight-point partial-volume sampling, 4-mm resampling and 2×2×4-mm anisotropy. Exact
box extents, noise smoothing, subvoxel offsets and resampling chains are stored.
Resolution-only differences are separated from intentional segmentation defects.
