# Physical equivalence of independent BEM formulations — M28

The audited continuous problem is quasistatic isotropic volume conduction with
piecewise constant conductivity, ideal point dipoles, continuous potential and
normal current across each interface, and an insulating outer boundary. Source
positions are MRI/RAS metres, moments A m, conductivities S/m, and free Cartesian
lead fields V/(A m). The three compartments merge brain and CSF at .33 S/m;
skull/scalp are .004/.33 S/m. This is not the four-interface M27 conductor.

MNE 1.13.2 uses vertex potential unknowns and linear triangle basis functions,
collocation/solid-angle coefficients and analytical primary dipole potentials.
Its default isolated-problem (IP) correction activates because skull/brain
conductivity is .012121, below its .1 cutoff. OpenMEEG 2.6.0 uses the symmetric
weak BEM formulation with piecewise linear interface potentials and piecewise
constant current unknowns, plus numerical integration of source and boundary
operators. The implementations are independent, but use shared canonical geometry,
source conventions, NumPy/SciPy and average referencing. Different discrete
solutions on the same finite mesh are expected; equality of the continuous BVP
does not prove equality of discretized operators or numerical convergence limits.

Stored triangles point outward. The OpenMEEG adapter explicitly permutes vertices
[1,0,2] for its inward convention. Actual C++ triangles are recovered through the
Geometry API and compared as oriented cyclic triangle-coordinate sets; effective
triangle hashes are retained. MNE's effective vertices, connectivity and compartment
conductivities are compared exactly after BEM creation. Neither adapter smooths
or remeshes the canonical input. Identity MRI/head transforms and MNE source_rr /
source_nn arrays verify source position and source-major XYZ ordering.

OpenMEEG HeadMat and DipSourceMat use order3/adaptive0/tolerance .001 in primary
comparisons. The treatment order5/adaptive1 jointly changes integration settings;
it is not a factorial separation of order, adaptivity or matrix/RHS integration.
SciPy pivoted LU solves the mixed potential/current system. Algebraic residual,
symmetry, reciprocal bilinear solve consistency, rank and retained singular spectrum
are recorded. A mixed-unit condition estimate is diagnostic, not a physical
constant. MNE's internal solve residual is not exposed here; no FEM PDE residual
or empirical current-conservation measurement is fabricated.

Both raw fields are retained locally, but their gauges are not asserted identical.
The same P=I−11ᵀ/32 is applied before every primary comparison and inverse.
Electrode-zero referencing is a separately reported sensitivity. Optimal scalar
alignment is descriptive only and never changes physical fields, thresholds or
reconstructions. Declared BVP equivalence and array correspondence support
PHYSICS_MATCH_CONFIRMED; they do not imply independent numerical agreement.

Primary references: [MNE BEM API](https://mne.tools/stable/generated/mne.make_bem_solution.html),
[MNE implementation](https://github.com/mne-tools/mne-python/blob/main/mne/bem.py),
[OpenMEEG tutorial](https://openmeeg.github.io/tutorial), and
[symmetric BEM formulation](https://pmc.ncbi.nlm.nih.gov/articles/PMC2949879/).
The local installed-source audit and software versions are retained with run receipts.
OpenMEEG is optional pinned CECILL-B software; no solver binary or model weights
are redistributed in Git. FEM_NOT_PERFORMED; PHANTOM_NOT_AVAILABLE.
