# Physical reference hierarchy — Milestone 27

Primary four-interface calculations use OpenMEEG **2.6.0**, symmetric surface BEM,
general geometry API, with SciPy pivoted LU on the assembled mixed potential/current
system. Homogeneous compartments have 0.33/1/0.004/0.33 S/m conductivities;
the outer air has zero conductivity. Potential and normal current are continuous
at interfaces. Ideal dipoles have zero net injected current. Average-reference
projection removes the potential gauge. Three Cartesian source columns have
V/(A m) units. Stored outward faces are explicitly adapted to OpenMEEG's inward
convention. Integration order is 3, adaptive levels 0, tolerance 0.001.

OpenMEEG is optional (`pip install '.[conductor]'`), pinned and isolated in child
processes. Its CECILL-B license concerns the solver software; no model weights,
participant data or external anatomical assets are redistributed. Ordinary CI
executes only small reference cases. Source/matrix pairing is checked explicitly.

| Level | Actual evidence | Result |
| --- | --- | --- |
| A exact | Independently derived central dipole in homogeneous insulating sphere: G = 3 r / (4 pi sigma R³) | Relative error 0.651776 / 0.132046 / 0.032174 / **0.007905**, levels 0–3. Finest passes frozen 2% target. |
| A semi-analytical | MNE four-shell sphere, off-centre sources, matched radii/conductivities/sensors | Errors 0.640878 / 0.147344 / 0.035495 / **0.009601**. MNE sphere is an approximation, not exact heterogeneous truth. |
| B | Same primary solver, six nonspherical heads, finest reference level 3 | All six pass frozen whole-model convergence criterion; not independent physics. |
| C three-layer | MNE linear collocation versus OpenMEEG symmetric BEM, matched level-2 controls, brain/CSF explicitly merged | **All six DISAGREEMENT**, relative differences 0.160884–0.176097, above frozen 0.10. Agreement NOT_ESTABLISHED. |
| C four-layer | No independent four-interface formulation executed | **NOT_ESTABLISHED**. |
| D | No documented empirical phantom recordings available | **PHANTOM_NOT_AVAILABLE**. |
| FEM | No FEM solver or PDE experiment performed | **NOT_PERFORMED**. |

MNE's standard BEM implementation and OpenMEEG wrapper support one or three
interfaces. They cannot silently replace the primary four-interface conductor.
The matched three-layer control deliberately merges brain and CSF at 0.33 S/m;
it is never compared as though it were the same four-layer physical model.
The observed disagreement is unresolved: discretization/formulation differences
are plausible, but no outcome-selected refinement or attribution establishes
its cause. Passing A/B does not override the failed C gate.

Maximum primary discrete algebraic residual was 3.24e-14; symmetry was exact to
stored precision. Bilinear reciprocal-solve and reference-null diagnostics are
recorded per call. These demonstrate algebraic consistency, not a FEM PDE
residual, measured reciprocity, or anatomical accuracy. Condition estimates mix
potential/current units and are reported as diagnostics, not physical constants.
Rank/singular spectra describe the projected field; coarse level 0 has rank 11
with 32 channels, while levels 1/2 have rank 31.

Primary sources: [OpenMEEG tutorial](https://openmeeg.github.io/tutorial),
[solver implementation](https://github.com/openmeeg/openmeeg),
[symmetric BEM paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC2949879/),
[MNE BEM documentation](https://mne.tools/stable/generated/mne.make_bem_solution.html),
[MNE implementation](https://github.com/mne-tools/mne-python/blob/main/mne/bem.py).

Sensor-level RMS field differences use 10 nA m Cartesian basis dipoles across
candidate positions, reported in µV; they are not population EEG waveform error.
Orientation column norms are in V/(A m). Average-reference invariance, projected
rank and singular spectra are retained separately from physical reference agreement.
