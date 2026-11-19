# Independent volumetric mesh replication

Gmsh 4.15.2 is an optional user-installed external mesher. Soma's worker supplies
four closed discrete surface entities, creates nested material volumes, assigns
brain/CSF/skull/scalp physical groups and uses native three-dimensional Delaunay
meshing. It does not invoke the M29 radial extrusion routine. The ordinary FEM
assembly remains the independently validated scikit-fem 12.0.2 full-subtraction
implementation: independent meshing is not a second FEM formulation.

`Mesh.MeshOnlyEmpty=1` preserves existing surface triangles. The worker checks
actual resulting tetrahedron/interface coordinates and connectivity, positive
signed element volumes, manifold facets, tissue-volume sums against signed surface
volumes and material adjacency. Mean-ratio quality is computed outside Gmsh; native
minSICN is recorded separately. Invalid or low-quality meshes are rejected, not
repaired by Soma. Gmsh's native interior optimization is part of mesh generation;
all boundary checks occur after it. General threads=1, algorithm3D=1 and random
seed30042 are fixed. The mesh-size schedule is25/15/9mm with minimum size1mm.

The independent homogeneous pilot uses1072/5148/23905 tetrahedra and reaches
9.647/2.367/.583% physical field error. Gmsh preserves the supplied polyhedral
boundary coordinates exactly in that pilot. This is independent interior meshing
on shared interfaces, not independent anatomical truth. The second surface path
rotates the angular sampling by17degrees around normalized[1,2,3], adds the32
canonical electrode directions, computes a new convex hull and maps the same M27
smooth boundary function. Its input/output facets also must match, while its
boundaries differ measurably from the original triangulation.

## License and distribution

The official [Gmsh license](https://gmsh.info/LICENSE.txt) is GPL version2-or-later,
with the specific Gmsh exception covering its listed Netgen, METIS, OpenCASCADE and
ParaView combinations. That is not a blanket permissive-linking exception. The
optional process loads the user's separately installed upstream package; Soma
vendors no Gmsh source, binary or SDK assets. Upstream license/source obligations
remain applicable to anyone redistributing Gmsh or a covered combined distribution.
No relicensing of upstream code is claimed. Scientific synthetic mesh outputs
contain no participant anatomy or restricted anatomical assets.

Reproduce with `pip install '.[fem,mesher,conductor]'` and
`soma source mesh-grid --parent experiments/milestone29 --output reports/mesh-grid-v30`.
Linux Gmsh wheels require the system GLU library (`libglu1-mesa`); the small native
CI checks install it explicitly. No external mesher is executed by an Explorer GET.
