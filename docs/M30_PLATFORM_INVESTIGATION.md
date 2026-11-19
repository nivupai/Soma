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

## Results from four actual runners (run 44364879928)

The original failure is reproduced without changing the comparator. Each Linux
report fails 15/192 entries against macOS Python3.11; Python versions agree within
each OS. Aggregate relative error is 0.004176368792957427 (0.417637%). The original
comparator therefore has30 failed comparisons across two Linux reports, representing
15 distinct sensor/source/orientation entries. The all-pairs table contains60 failed
comparisons across four OS-crossing pairs. Full precision values, indices, units,
relative deltas and exact applied tolerances are retained in the new evidence directory.

Failures have median reference magnitude10.3813 V/(A m), versus42.4377 over all192
entries. Their magnitudes span1.5587–34.7774 V/(A m); none is below1 V/(A m).
Smaller signals are more affected, but the failure is not limited to numerical zeros.
Neither sensors nor source columns are excluded.

Both native meshes have212 nodes and1072 tetrahedra. Their numbering-independent
coordinate/connectivity/material fingerprints differ: they are physically different
interior discretizations, not just different array orderings. Maximum bidirectional
vertex-set distance is29.776 mm (interior point sets, not an interface Hausdorff
error). All actual tissue interfaces remain valid and preserve their supplied facets.
Native source arrays are identical; native sensor coordinates differ by at most
1.38778e-17 m. Boundary construction also has floating-point differences.

Identical serialized boundary inputs do not produce identical native meshes either:
interior vertex-set distance is29.805 mm. Hence boundary roundoff alone does not
explain native mesh variation. Gmsh4.15.2, algorithm1, one thread, seed30042, size
limits and captured numerical options match across runners.

| Controlled construction | Linux/macOS relative field delta | Failed entries |
| --- | ---: | ---: |
| Original native mesh | 0.417637% | 15 |
| Canonical boundary numbering | 0.459490% | 16 |
| Identical serialized boundaries | 0.439443% | 10 |
| Alternate seed30043 | 0.369340% | 14 |
| Mesh.Reproducible enabled | 0.439443% | 10 |
| Both random perturbation factors zero | 0.428892% | 16 |

No tested supported configuration produces a numbering-independent identical native
mesh across these operating systems, and none clears the original elementwise
criterion. These are causal/exploratory controls, not replacement M30 results.
No favorable variant is selected to obtain a passing gate.

On the serialized mesh, the first four-run fields agree to1.12e-14 relative, with
zero elementwise failures. Stiffness and RHS relative differences are approximately
1.48e-16 and2.08e-16. Source/sensor ordering and source-major XYZ conventions match.
All computations use float64. Different native BLAS implementations and sparse
arithmetic do not explain a0.418% discrepancy on a common mesh.

Changing sparse LU permutation, reversing nodes/elements, applying an even local
tetrahedral permutation, and changing subtraction quadrature from8 to6 leave
cross-platform common-mesh differences below2.40e-14. The local q6/q8 field change
is approximately9.33e-8 relative. A local sensor-only roundoff control changes
fields by6.67e-17 relative. No dipole subtraction, conductivity, boundary condition,
precision, summation, regularization or solver implementation is changed.

The first common-mesh diagnostic retained each environment's native sensor values,
including the measured1.39e-17 m difference. The final diagnostic explicitly loads
both source and sensor arrays from the serialized fixture, removing even that
input-roundoff confound. It also records NumPy/SciPy BLAS build identities and an
independent C-runtime random-sequence probe after all solves. Actual final-run
receipts are recorded in the PR and local completion record, without rewriting
this first-run evidence.

## Upstream mechanism and limits of attribution

The official Gmsh4.15.2 source archive was independently downloaded and hashed.
Its Generator.cpp seeds the C runtime PRNG, and the Delaunay path uses C-runtime
random draws for perturbations and point-location choices. This is a credible
nonportable mechanism even with a fixed integer seed. Floating-point geometric
predicates, native optimization and platform builds may also contribute. A unique
internal cause has not been proven with an instrumented upstream build; the
investigation establishes the mesh-generation/discretization layer as the dominant
source, rather than claiming a specific BLAS or FEM bug.

The bounded supported-option controls do not establish portable native mesh
identity. Resolving that remaining upstream behavior requires further native
instrumentation or a provenance-reviewed deterministic upstream change. Replacing
the required native check with the serialized-mesh control would hide the failure
and is deliberately not done. The scientific gate remains FAILED and PR15 must
not merge. This is an unresolved portability limitation, not a successful fix.

## Verification and security update

Local full Python suite:1652 passed (all original1650 plus2 diagnostic tests).
Offline suite:1635 passed,17 deselected. Frontend48 and configured Playwright23
passed. An initial browser invocation without the existing local protocol/data
configuration failed its protocol-history test and skipped its local-data test;
the complete configured invocation then passed without changing any test.
Ruff, formatting, strict mypy over294 source files, pip consistency and Python
audit passed. Package and final exact-head CI receipts are retained separately.

First diagnostic CI:12/13 jobs pass; only compare_mesh_grids.py fails. Every
individual native-mesher platform run passes its own physical/analytical checks.
The unchanged full npm audit now passes because GitHub withdrew
GHSA-fc5q-39xc-vjpf at2026-11-18T15:38:56Z. Picomatch remains4.0.7; no patched
release is listed. This is an upstream advisory withdrawal, not a dependency fix,
audit suppression or proof of absence of every possible vulnerability.

Original M26–M30 results, existing tests and the original comparison script are
hash-protected. The46 M24 archived model files are checked independently. New
synthetic diagnostic evidence is under experiments/milestone30-platform-investigation;
no historical measurement or manifest is rewritten. No M31 work is started.
