# Independent matched BEM/FEM comparison

The primary model has brain .33, CSF 1, skull .004 and scalp .33 S/m, insulating
exterior, MRI/RAS metres, 32 canonical shared scalp nodes and identical sensor
average reference. OpenMEEG 2.6.0 symmetric P1-potential/P0-current BEM is compared
with independently assembled scikit-fem 12.0.2 continuous P1 full-subtraction FEM.
They solve the same declared continuous problem using different finite spaces.

All six heads use all 12 independently generated M27 truth locations and 12 fixed
candidate probes (indices 0:6 and24:30). Candidate probes are not independent
source draws. XYZ lead columns are repeated orientations, not independent heads.
Unscaled fields are primary. Optimal scalar alignment and signed correlations
are explanatory diagnostics and never change acceptance. All six finest aggregate
comparisons must pass the prespecified 10% engineering gate. Passing does not
mean every source, moment or human anatomy has less than10% error.

FEM/BEM share declared geometry and inputs but have independent assembly, source
representation and numerical solves. Their matching mesh facets are audited against
actual arrays, not inferred only from a seed. Homogeneous and concentric layered
references independently constrain shared geometry/discretization biases. Identical
small pairwise error can coexist with larger error against the smooth sphere.

The three-layer controls retain the .081 m surface as an equal-conductivity FEM
partition and merge brain/CSF to .33 S/m for MNE/OpenMEEG, using the .0828 m boundary.
This is physical equivalence, not a comparison of the four-layer CSF=1 model with
an incompatible merged conductor. Head0 and heldout head 5, levels2/3, use the same
24 positions and sensors. Their estimand differs from M28's 60-position primary
array and from M27's original four deep sources plus cap; old numbers are retained.

Twelve independently drawn sources are nested in each of six head generators.
Intervals use the inherited M27 family-stratified head-then-source bootstrap after
noise averaging. Sensor channels, XYZ axes, meshes and inverse draws are repeated
computations. Coverage is uncalibrated; intervals are conditional simulation
summaries, not human population confidence intervals.
