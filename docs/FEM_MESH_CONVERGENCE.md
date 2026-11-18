# Conforming four-compartment tetrahedral meshes

The experiment reuses the six deterministic M27 head identities, two each prolate,
oblate and smoothly asymmetric. Each angular triangle is extruded through radial
shells and split into three tetrahedra using one global vertex ordering. A central
cone completes the brain. Brain has four radial intervals per refinement step;
CSF/skull/scalp have one each. Radial steps 1/2/3 accompany angular levels 1/2/3.

The three resolutions have 295/2269/13483 vertices and 1520/12800/78,080 tetrahedra.
All four interfaces preserve the input triangle connectivity; the volume interface
coordinates differ from the supplied BEM coordinates only by floating-point roundoff,
which is independently quantified in the audit. No smoothing, external meshing or
independent electrode projection is hidden. Sensors are shared existing scalp nodes.
The meshes approximate the smooth generating surface by planar facets.

Checks reject nonpositive tetrahedral volumes, low mean ratio, nonmanifold facets,
missing outer facets, and tissue-interface facet discrepancies. Quality uses
12(3V)^(2/3)/sum(edge_length²), equal to one for an equilateral tetrahedron. Material
labels are checked against the four expected regions. Geometry is restricted to
nested star-shaped generated models; this is not a general human MRI mesher.

The homogeneous pilot on an independently generated scikit-fem ball uses
512/4096/32,768 tetrahedra and reaches 6.58/1.68/0.462% field error. The matched radial
pilot reaches 10.56/2.51/0.608% across the three stated meshes. Coarse exploratory q4
failed current compatibility. The frozen q8 full study retains a separate coarse
homogeneous failure; it is not removed to improve convergence plots.

Field convergence is measured independently of algebraic residuals. Uniform angular
and radial refinement changes discretization and polyhedral approximation together.
Head0 controls hold angular level 2 fixed while changing radial steps and quadrature.
These controls bound contributors; three levels do not establish an asymptotic order,
a posteriori bound or exact nonspherical truth. Actual rows and figures are in
`experiments/milestone29` and the results report.
