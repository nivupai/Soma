# M29 frozen independent FEM protocol

Parent: e68fa127dc65fbf39d43f574beacf64a9a31c4d1, unmerged PR #13.
M29 is developed and reviewed against that branch; no merge to main while its
npm security audit fails. No history rewrite or security exception is authorized.

The machine-readable design and M19 declaration seal are committed before final
layered or nonspherical outcomes. The homogeneous feasibility pilots precede this
seal: scikit-fem 12.0.2 installed successfully; full subtraction on a ball reaches
0.462% aggregate error and the matched radial tetrahedral mesh reaches 0.608%.
The first exploratory q4 coarse radial mesh failed the current-compatibility
check; q8 was selected in the pilot, before the final protocol. That failure is
retained. A pilot JSON serialization failure was corrected and rerun.

See `configs/fem-reference-v29.json` for exact sources, geometry, three mesh levels,
conductivities, reference, source subtraction, gates, controls, resource budget,
inverse settings and uncertainty. The generic workflow declarations seal the
physical design; they are not a claim that the generic replay engine ran FEM.
The explicit experiment uses the inherited M27 generator and noise schedules.

The FEM uses conforming P1 Galerkin full subtraction, an independently assembled
volume formulation. It reuses physical mesh/source definitions, not OpenMEEG
assembly or MNE source interpolation. Four surface interfaces remain exact
triangles of the BEM mesh. Each angular prism is split with a global vertex order;
all tetrahedra and material-interface facet correspondence are checked.

The continuous source is p·(x−x0)/(4πσ0|x−x0|³). The correction obeys
A(uc,v)=−∫(σ−σ0)∇u∞·∇v−∮σ0∂n u∞v. The contrast load is evaluated only outside
brain, where the singularity is absent. A single correction gauge DOF is pinned;
the RHS compatibility defect is measured before subtracting its algebraic mean.
The same sensor average reference is applied to total physical potentials.
No arbitrary nodal dipole force is inserted. P1 spatial and quadrature errors
remain independent of algebraic residuals.

Independent four-layer agreement requires all six finest aggregate physical
comparisons within 10%; scalar alignment is diagnostic only. The analytical
homogeneous gate is 2%, independently checked. Failures remain in the tables.
No four-layer claim follows solely from homogeneous convergence. The finest FEM
is an approximation, and shared FEM-generated inverse truth cannot establish
solver superiority. No human, empirical phantom or population accuracy is claimed.

## Explicit post-outcome metadata correction

Revision2 retains the original seal and corrects only generic inverse/reconstruction
implementation descriptors to `source.uncertainty.kernels` and
`experiments.source_uncertainty.source_metrics`. The original inherited descriptors
incorrectly named the forward function. No physical design, tolerance, source,
noise, inverse grid or regularization changes. Outcomes had already been inspected;
this is explicitly a post-outcome correction, not a pre-outcome registration.
The entire frozen study is repeated under revision2 and compared numerically with
the original, including heldout head5. Original scientific outputs are preserved.
