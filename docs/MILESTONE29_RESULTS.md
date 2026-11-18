# Milestone 29: independent four-layer volume/surface validation

This work is based on M28 e68fa127dc65fbf39d43f574beacf64a9a31c4d1,
not M27 main. M28 PR #13 remains open with its required upstream npm security
failure. M29 is a dependent branch and must not merge into main before M28.

The physical protocol was committed at 7e4205f after homogeneous feasibility
pilots and before final layered/nonspherical outcomes. Revision2 at 362955e
explicitly corrects inherited generic inverse/reconstruction implementation
metadata after outcome inspection; it does not change any physical input,
target, mesh schedule, inverse grid or regularization. Original seals and
results are preserved. The full experiment is repeated under the amended seal;
byte comparisons of physical fields and numerical tables distinguish this
correction from a new experiment or retrospective target selection.

## Independent physical reference

The reference is scikit-fem 12.0.2 (BSD-3-Clause), continuous P1 Galerkin FEM with
full dipole subtraction and SciPy sparse LU. It installed and solved the
homogeneous analytical benchmark before the full study was frozen. This is an
independent EEG-specific assembly using a maintained general FEM library, not an
OpenMEEG wrapper. No FEniCSx/GetDP or empirical phantom evidence is claimed.
[Formulation, units, source treatment and license](FEM_FORWARD_REFERENCE.md).

The independent ball pilot reaches .462% homogeneous-sphere field error at
32,768 tetrahedra. The matched radial pilot reaches .608% at78,080 tetrahedra.
The full matched study uses four interfaces and 32 identical nodal sensors, all
XYZ orientations of 24 locations/head: 12 fixed candidate probes and12 original
independent M27 off-grid draws. The declared four conductivities are
brain .33, CSF 1, skull .004, scalp .33 S/m; the exterior is insulating.

Actual FEM interfaces retain BEM connectivity. The maximum coordinate discrepancy
from radial interpolation roundoff is1.40e-17 m; source and sensor arrays are exactly
equal. Native OpenMEEG geometry is independently inspected by the existing adapter.
This is the same continuous physical BVP, with different discrete spaces and
source treatments, rather than merely two arrays produced from the same seed.

## Analytical and four-layer field results

| Reference / solver | Level1 relative error | Level2 | Level3 |
| --- | ---: | ---: | ---: |
| Homogeneous radial FEM | retained current-compatibility failure | 2.808%|.6543% |
| Homogeneous OpenMEEG |25.586%|6.653%|1.769%|
| Four-layer sphere FEM versus independent transmission series |16.091%|4.032%|1.052%|
| Four-layer sphere OpenMEEG versus same series |16.130%|3.996%|1.042%|

The homogeneous finest aggregate2% gate passes. The concentric reference solves
potential/current transmission and outer zero flux independently for each spherical
harmonic; it is not MNE's approximate sphere model. The 48-versus96-term truncation
tail relative difference (3.04e-9) and algebraic transmission residuals are reported separately. Error against
the smooth sphere includes planar-boundary approximation; pairwise BEM/FEM agreement
can be smaller than either solver's analytical error.

| Synthetic head | Finest unscaled OpenMEEG/FEM difference |
| --- | ---: |
|0 prolate|0.4289%|
|1 prolate|0.3316%|
|2 oblate|0.6069%|
|3 oblate|0.4146%|
|4 asymmetric|0.3132%|
|5 asymmetric|0.3042%|

All six finest aggregate comparisons pass the unchanged 10% engineering target.
This establishes bounded independent four-layer numerical agreement on these
synthetic geometries, not a certified error bound for arbitrary sources or human
anatomy. The finest FEM is not exact truth. Off-grid source errors range .1608–2.1340%; orientation-specific aggregate ranges are
X .3373–.4261%, Y .2554–.8008%, Z .2972–.5980%. Per-source, orientation, scalar/pattern,
rank/conditioning and depth tables retain the actual physical units and outcomes.
Scalar alignment is diagnostic only and is never applied to acceptance.

Same-solver level 1→2 relative changes are11.36–14.57% FEM and11.71–11.94% OpenMEEG;
level 2→3 changes are2.94–3.13% FEM and2.92–3.01% OpenMEEG. These are repeated
computations, not independent participants or an asymptotic-order estimate.
At fixed angular level 2 on head 0, radial steps1 and3 change FEM fields by .2127%
and .0588% relative to primary steps2. Reducing quadrature8 to4 changes fields by
.1617%. These controls bound contributors; they do not uniquely decompose every
remaining geometry, quadrature and discretization error.

## Implications for M28

| Matched three-layer control | OM/FEM level 2 | MNE/FEM level 2 | OM/FEM level 3 | MNE/FEM level 3 |
| --- | ---: | ---: | ---: | ---: |
|head 0|1.3793%|21.7414%|.3307%|10.7670%|
|heldout head 5|1.0504%|21.5365%|.2434%|10.6265%|

The FEM retains an artificial equal-conductivity brain interface while MNE/OpenMEEG
merge brain+CSF at .33S/m. The physical conductors are equivalent. The new independent
reference is much closer to OpenMEEG in these two controls. Combined with M28's
refinement and IP controls, this strengthens attribution to MNE finite-formulation
bias at the tested resolutions. It does not uniquely identify every remaining
kernel/discretization contribution or prove a common asymptotic limit. It does not
rank solver accuracy for all geometries. This24-location estimand differs from
M28's60-position primary array and M27's original four-source cap comparison.
All historical failed gates, thresholds and files remain unchanged.

## Source localization and uncertainty

The frozen 12-candidate grid is sparse and gives poor absolute localization. At
level 2 and .05µV noise, finest independent FEM off-grid truth gives:

| Inverse | FEM peak error(mm) | OM peak error(mm) | Paired OM−FEM conditional interval(mm) |
| --- | ---: | ---: | --- |
|Tikhonov|55.506|55.620|.114[−.014,.268]|
|MNE inverse|55.968|56.234|.267[.091,.508]|
|dSPM|56.589|56.617|.028[−.060,.109]|

FEM/OM dispersion is67.321/67.550mm Tikhonov,68.052/68.135mm MNE inverse,
and66.552/66.606mm dSPM. Physical peak biases are−.184/−.194 and−.692/−.694,
respectively. dSPM amplitudes are normalized, not physical current estimates.
Mean nearest-grid error is 53.441 mm. Paired peak displacement and relative resolution differences
are retained. Shared FEM truth favors neither a human nor a clinical claim;
it also leaves correlated numerical validation that must be acknowledged.

Uncertainty resamples heads within the fixed two-per-family strata, then12 sources
within head, after averaging noise draws. There are six independent head generators
and72 independent off-grid draws, not 7,344 independent participants. Intervals are
conditional simulation summaries with uncalibrated coverage. The study is too small
for broad ensemble or human-population claims.

## Failures, resources, artifacts and limits

The frozen run has62 successful forward configurations and one retained failure:
coarse homogeneous FEM current-compatibility defect .001214 exceeds the fixed .001
limit. All 7,344 inverse rows compute. The earlier exploratory q4 pilot failure and
JSON serialization/export mistakes are retained locally and described explicitly;
they are not counted as successfully computed physical configurations.

The three volume levels use295/2269/13483 nodes and1520/12800/78,080 tetrahedra.
Every completed volume mesh has positive elements, valid material facets and minimum
mean ratio above .1006. The amended repeat takes 581.747 seconds. Maximum solver-child RSS is
989.484 MiB for FEM and 1116.594 MiB for OpenMEEG, including imports. The original
run takes 606.365 seconds and retains its separate resource measurements.
Algebraic residuals and current compatibility are distinct from spatial convergence.

`experiments/milestone29` contains actual physical operators, fields, geometry audits,
mesh/label data, convergence and source tables, paired inverse and uncertainty data,
12 scientific figures, exact executed source archives, hashes, M19 seals and native
M17 result envelopes. The Explorer displays only reviewed read-only synthetic
aggregates. No remote scientific execution endpoint or new frontend dependency is
introduced. [Verification](MILESTONE29_VERIFICATION.md) records actual software gates.

There is no individualized human MRI/EEG validation or measured phantom validation.
Future work should independently reproduce nonspherical results in a second
volume mesher/FEM codebase, refine deeper/shallow sources and sparse inverse-grid
limitations, and calibrate uncertainty without correlated truth. That is a proposed
Milestone30 direction only; M30 has not started. M29 remains dependent on unmerged
PR #13 while npm audit is blocked; no merge or postmerge result is claimed.
