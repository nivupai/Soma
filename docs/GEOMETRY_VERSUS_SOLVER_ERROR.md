# Distinguishing geometry, volume mesh and solver effects

The four-compartment target uses brain .33, CSF1, skull .004 and scalp .33S/m,
MRI/RAS metres, ideal Cartesian dipoles, insulating exterior and one common sensor
average reference. All32 electrode coordinates are deliberate shared vertices of
both surface samplings; there is no independent scalp projection. This sensor
constraint is a shared design feature, not fully independent surface generation.

A reuses the immutable M29 radial FEM/standard OpenMEEG physical operators after
checking the parent artifact manifest and physical source/sensor/conductivity
hashes. B compares new Gmsh FEM against OpenMEEG on the same input interfaces.
C compares Gmsh on separately sampled boundaries against the original BEM
approximation of the same smooth target. The latter combines geometry and solver
error and is not labeled matched physical geometry. Additional BEM calculations
on the alternative finest boundaries separate a matched alternative comparison
from a BEM-only geometry perturbation. D compares independently meshed homogeneous
and four-layer concentric spheres against the applicable independent analytical
solutions, including the M29 harmonic transmission series.

Actual tetrahedral boundary facets, not just generator seeds, are checked. Standard
and alternative inputs are generated independently of Gmsh's interior meshing.
Surface mismatch is sampled bidirectionally at vertices and facet centroids against
the finest standard polyhedral reference, with explicit millimetre units. Those
samples are not a certified continuous Hausdorff distance and the standard finest
surface is not exact smooth anatomy. No zero geometry claim is made for differing
surface representations.

All fields remain physical V/(A m), and RMS differences use10nA m moments in µV.
Optimal scalar alignment and pattern correlation are descriptive metrics; they
never replace unscaled acceptance. Mesh convergence, source/orientation effects,
lead-field conditioning, algebraic residuals and geometry deviation are reported
separately. Neither a small residual nor pairwise agreement proves absolute accuracy.
