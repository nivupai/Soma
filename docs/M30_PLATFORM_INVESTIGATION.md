# M30 cross-platform investigation (post-outcome addendum)

This investigation follows the failed gate at `beb0fb7` / Actions run
44282716080. It does not amend the frozen M30 study or its numerical results.
The original comparator remains unchanged: elementwise `rtol=0.02`,
`atol=0.01 V/(A m)`, applied against the first sorted platform report.
Aggregate norms are diagnostic summaries, never replacement acceptance criteria.

## First controlled diagnostic

The original reports did not retain volume connectivity or matrix assembly data.
A separate diagnostic now records native vertices, positive tetrahedra, tissue
labels, physical interface audits, raw and numbering-independent mesh hashes,
Gmsh versions/options, sources/sensors, sparse stiffness matrices, reduced RHS
vectors, float precision, library versions and sanitized BLAS metadata.

Controls use (1) original native construction, (2) canonical boundary numbering,
(3) identical serialized boundary inputs, (4) experimental upstream
Mesh.Reproducible, (5) zero random perturbation factors. All remain exploratory;
none changes the native scientific gate. Each failed control is retained explicitly.

A synthetic local native mesh was serialized into
`configs/mesh-grid-control-v30.json` after the original failure. Solving that exact
mesh on all four environments separates native mesh generation from assembly/LU
arithmetic. Further controls vary node/cell/local positive orientation ordering,
LU permutation and quadrature. This fixture is not a reference field or a
platform-specific expected answer, and does not replace the native-meshing check.
No participant data, licensed anatomical assets or upstream code are included.

`scripts/diagnose_mesh_grid_entries.py` produces both all-pairs and original-gate
failure tables, including source-major XYZ indices, field values, absolute/relative
deltas, exact per-entry tolerances and small-field indicators. Relative difference
at a zero reference entry is explicitly undefined. A 1 V/(A m) small-field cutoff
is descriptive, not an exclusion or acceptance threshold.

The same four GitHub runners execute the diagnostic. Their original native field
comparison remains enabled and is allowed to fail visibly while the cause is
investigated. The npm audit remains independently required. No merge is permitted
with either check failing; no M31 work is started.
