# M30 frozen independent mesh and inverse-grid protocol

Parent M29 commit88fcda2f2d4fd4f215294fac966fa180a6594df9, dependent PR14 and PR13.
The branch targets M29 until both predecessors safely merge. Security gates remain
unchanged and no dependent merge is allowed while npm audit is blocked.

The design and M19 seal are committed after independent mesher feasibility pilots,
before final fields or localization outcomes. Local sealing is not external
preregistration. The immutable design records all physical parameters, source
identities, geometry alternatives, numerical gates, inverse grids, noise,
regularization, uncertainty and resource limits. Generic workflow declarations
seal the design; they do not claim generic replay execution or its RNG schedule.

The official Gmsh4.15.2 pilot preserves all four original input surface facets and
coordinates. Independent P1 FEM homogeneous error reaches .583% after9.65/2.37%
at coarser levels. A second triangulation uses a rotated angular sampling plus
32 shared electrode vertices; its valid mesh is independently labeled and audited.
The initial exploratory facet check incorrectly compared oriented signatures
against index-sorted tetrahedron facets; it was corrected to compare unordered
physical triangles, with positive element orientation checked separately. No
invalid tetrahedra were repaired or silently accepted.

Before seeing localization outcomes, Cartesian spacings30/20/15mm give33/147/341
candidates inside every level2 brain. These grids are not assumed nested or
monotonically superior. The old12-candidate grid is retained as a paired baseline.
Truth is finer Gmsh FEM at original independent M27 source draws. All models and
grids receive identical measurement vectors and frozen regularization. Correlated
FEM truth, MNE's intrinsic covariance normalization and source-grid effects remain
explicit limitations. Alternative-geometry truth is a separate paired sensitivity.

All intended failures are retained. Same-interface agreement and differing-boundary
comparisons have distinct interpretations. Ten percent is the continuity engineering
target, not a human accuracy claim. Whole matrices and large experiments stay outside
ordinary CI. The small external-mesher platform check has its own declared2% relative
plus .01V/(A m) numerical tolerance, not a substituted scientific acceptance gate.
