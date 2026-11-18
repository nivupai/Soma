# Milestone 28 — actual independent BEM diagnostic results

Soma v0.28.0 continues from main `31e389db42c5cd3bfd2bca0e0a83958257744fcf`.
The physical design was committed at `61973db` before new reference outcomes;
design SHA256 is `70aa0942ed36ae6b2b75c1fc64fe13bfb5964d079c2d42811b37746923cbf596`.
Local sealing is not external preregistration. M26/M27 outputs remain immutable.
The original seal inherited contradictory four-layer descriptive metadata and
stale generic summary descriptors. Explicit post-outcome revisions 2 and 3 retain
that seal, correct those declarations and clarify generic replay-policy scope;
the original three-layer design, every physical input and the .10 target remain
unchanged. The complete study is repeated under the corrected final seal,
including heldout head5, with numerical identity checked against the first run.
The corrections are not claimed to have preceded the original outcomes.

## Findings

The original six 16.088–17.610% MNE/OpenMEEG discrepancies were reproduced exactly
before altering adapters. Canonical geometry, conductivities, MRI/RAS units,
source ordering and sensor/reference contracts match. Native geometry inspection
found no hidden remeshing or unit transformation; maximum MNE sensor projection
was 3.54e-17 m. The solvers represent the same declared continuous physical BVP,
with different finite numerical formulations.

The exact homogeneous limiting reference passes its frozen 2% finest aggregate
gate: OpenMEEG 1.412%, MNE .472%. Layered spherical differences against the explicitly
approximate MNE sphere reference reach 1.028% / 9.063%. The independent nonspherical
field differences decrease to **11.709–12.208%**, still failing the unchanged
**10% target in all six heads**. The new full 60-location primary metric differs
from M27's four deep locations and cap. No subset, reference choice or scalar
alignment is used to manufacture a pass.

Controlled evidence identifies finite interface/formulation discretization as
a contributor: the discrepancy exists in concentric layered geometry, decreases
under uniform refinement and responds to interface-specific refinement in both
head0 and heldout head5. Higher integration changes fields only .003–.004%; removing
MNE's IP correction worsens the gap about 2.45-fold. This is a bounded explanation,
not a unique decomposition of all remaining numerical bias. High pattern
correlation coexists with magnitude differences; a common asymptotic limit has
not been demonstrated. [Detailed attribution](INDEPENDENT_SOLVER_DIAGNOSTICS.md)
retains negative findings and denominator/reference distinctions.

## Source reconstruction consequences

Known truth uses finer OpenMEEG level3 off-grid fields; the estimates use levels1/2,
48 fixed M27 candidates, unchanged regularization and the M27 shared noise schedule.
Shared OpenMEEG truth dependence is explicit; peak location alone cannot rank
physical solvers. At level2 and .05 µV noise:

| Inverse | OpenMEEG estimate peak error (mm) | MNE estimate peak error (mm) | Paired MNE−OM conditional interval (mm) |
| --- | ---: | ---: | --- |
| Tikhonov | 23.569 | 22.791 | −.778 [−1.755, −.112] |
| MNE | 22.709 | 22.705 | −.004 [−.435, .365] |
| dSPM | 21.210 | 21.322 | .112 [−.055, .319] |

Spatial dispersion is 45.417/43.244 mm for Tikhonov, 42.670/43.259 for MNE and
41.553/41.684 for dSPM, in physical-forward order OM/MNE. Peak current bias ratios
are −.800/−.750 and −.890/−.866 for the physical-amplitude methods. dSPM amplitude
is normalized, never compared as a physical moment. Linear resolution changes
and paired source-level tables are retained. Intervals resample heads within
fixed families then sources within head after noise averaging, using the inherited
M27 bootstrap schedule; they are conditional simulation summaries with uncalibrated
coverage, not human confidence intervals. Sensors/components/meshes are not participants.

## Coverage, provenance and limits

The study computed **75 forward configurations**, with **zero numerical failures**,
and **14,688 inverse rows**, all successful. Six independent generated heads,
12 independent off-grid generators/head, 48 additional fixed candidate probes,
32 shared nodal sensors, three mesh levels and signed XYZ/arbitrary moments are
identified separately. All planned factors include heldout head5. Original cap
controls and unsuccessful scientific gates remain visible.

Primary runtime was **335.469 seconds**; maximum solver-child peak RSS was
**718.953 MiB**, including imports. Resource limits were not relaxed. Public
`experiments/milestone28` contains machine-readable field/source/orientation,
reference, factor, cross-refinement, inverse, uncertainty and resolution tables,
figures, native M17 result envelope, M19 seal and exact content hashes. Executed
source bytes are archived as text with a source index matching recorded hashes.
Subsequent changes tighten invalid-input guards and correct an unused SDK import;
physical assembly and the frozen numerical outcomes are unchanged. Independent
NumPy/SciPy postprocessing checks metrics outside the primary adapter.

[Physical formulation](SOLVER_PHYSICS_EQUIVALENCE.md),
[geometry audit](MATCHED_GEOMETRY_AUDIT.md), and
[discretization study](BEM_DISCRETIZATION_STUDY.md) describe the evidence scope.
Independent four-layer agreement remains **NOT_ESTABLISHED**; **FEM_NOT_PERFORMED**;
**PHANTOM_NOT_AVAILABLE**. No human MRI source modeling or empirical phantom
accuracy is established. Proposed M29 is a separately frozen analytical/refinement
investigation of the remaining layered discrepancy. M29 has not started.


## Publication status

Scientific implementation and numerical evaluation are complete, with the failed
agreement gates retained. Publication is subject to all required software/security
checks. On 2026-11-17, an upstream unpatched picomatch advisory blocks the existing
npm audit gate; see MILESTONE28_VERIFICATION.md. No successful merge or postmerge
verification is claimed while this required gate fails.

All 96 numerical CSV tables are byte-identical across the original and both corrected-seal runs.
The final native envelope uses revision 3 and passes direct read-back; earlier
seals, source snapshots and native receipts remain available for audit.
