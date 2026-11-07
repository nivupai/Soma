# Conductor geometry and readiness

Three ordered interfaces are inner skull, outer skull and scalp. Actual sample
archive inspection resolves all default `.surf` symlinks to participant FLASH
products. The original protocol's watershed assumption was incorrect and remains
visible in the sealed files; the [amendment](INDIVIDUAL_HEAD_MODEL_AMENDMENT.md)
records the correction after exploratory computations. FLASH aliases are not
independent alternative anatomical models. Optional `anatomy watershed` delegates
to MNE/FreeSurfer and refuses overwrite; generation was not executed locally.

The adapter inventories native vertices/faces/finite coordinates separately.
Full topology, geometry and quality acceptance applies to the actual MNE ico3
solver surfaces (642 vertices, 1,280 faces per boundary), not every original
high-resolution surface. Native inventory is not full native geometric QC.

Soma reuses the Milestone 7 checks: connectedness, edge multiplicity, vertex
links, duplicate/degenerate faces, oriented edges, positive reliable signed
volume, nonadjacent triangle intersections, solid-angle containment and exact
triangle separation. Conservative centroid-sphere broad-phase searches avoid
unbounded dense all-pairs allocation. Required minimum separation is 0.1 mm,
intersection tolerance 1e-8 m, minimum triangle quality 0.01. Actual sample solver
meshes have no detected self-intersections/nonmanifoldness; adjacent-layer gaps
are approximately 3.238 and 3.476 mm. Passing these tests establishes scoped
computational geometry, not histological or physiological boundary truth.

Readiness separately reports topology, geometry, anatomical evidence, coordinate
consistency, sensor compatibility and solver mesh quality. A false condition
produces FAIL; an unsupported required condition produces INDETERMINATE. The real
sample is computational PASS and overall **INDETERMINATE**, with anatomical
evidence unsupported. Synthetic known shells can PASS their mathematical scope.
Neither outcome is clinical/anatomical certification. The SPM foreground mesh
from Milestone 7 still fails and is never used as a conductor boundary.

MNE three-layer BEM is piecewise homogeneous and isotropic. Baseline assumed
scalp/skull/brain conductivities are 0.3/0.006/0.3 S/m. Model objects store surfaces
inner→outer (IDs 1/3/4); the MNE solver receives outer→inner (4/3/1), with
conductivities assigned in that order. Integration tests independently regenerate
a forward and verify IDs, conductivities, channels and fixed-normal correspondence.
Sources use participant white ico3, 5-mm minimum inner-skull distance.

EEG digitization remains unchanged. MNE's standard EEG computation projects
contacts onto the scalp using its barycentric surface procedure. Distances and
inward contacts are reported, including one approximately 3.24-mm inward contact;
gross incompatibility beyond 30 mm fails. The abandoned 3-mm inward rejection
was an unregistered development guard, disclosed in the amendment. Projection
is a solver assumption, not anatomical ground truth or electrode correction.
See [MNE forward implementation](https://github.com/mne-tools/mne-python/blob/main/mne/forward/_compute_forward.py).

Numerical accuracy is checked independently against MNE's analytical layered
sphere reference, not only another BEM call. Relative full-operator discrepancies
are 30.36% and 18.66% at subdivisions 1 and 2. These are substantial finite-mesh
errors, reported separately from registration error; the analytical reference
also uses an established approximation. No continuum-accuracy threshold was
retrospectively selected. A development-only subdivision-3 check gave 7.66%; it
is exploratory and not a substituted primary result.
