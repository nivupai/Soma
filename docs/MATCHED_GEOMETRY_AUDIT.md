# Canonical geometry and source/sensor audit — M28

Every paired calculation uses one canonical vertex array, interface identity and
triangle connectivity, not merely matching generator seeds. Geometry, source
positions/basis/order, sensor coordinates, conductivity units/assignments, frame
and average-reference matrix have separate hashes. Contracts must compare exactly.
Native geometry inspection checks both solvers' effective models. All 75 executed
configurations completed, with no geometry, solver or ordering rejection.

The six M27 heads retain their exact generator. Three-layer controls use M27
interfaces 1/2/3, inner radius nominally 82.8 mm, rather than comparing the original
four-interface model with a three-interface approximation. Uniform subdivisions
1/2/3 contain 42/162/642 vertices and 80/320/1280 triangles per interface. Mixed
interface controls refine exactly one interface to level3 while retaining others2;
all remain closed, outward oriented and nested under the existing geometry checks.
No invalid geometry is silently repaired.

Primary sensors are the first 32 level-1 icosphere vertices mapped to the analytic
scalp. These same nodes occur at every refinement level. Both solvers receive
exactly those coordinates. MNE's effective projection distance was at most
3.54e-17 m, numerical roundoff, so no hidden scalp reprojection explains the gap.
The original M27 interior-triangle Fibonacci sensor cap is retained as a separate
physical sampling control, using one precomputed array for both solvers.

The 48 M27 candidate positions and 12 independent off-grid sources are concatenated
in a fixed order. Every source has XYZ lead-field columns; MNE source_rr/source_nn
are checked, and OpenMEEG's explicit unit source matrix follows the same ordering.
Positive/negative arbitrary 10 nA m moments are evaluated from these linear fields;
independent analytical calibration and adversarial tests detect sign reversal,
axis or source permutation, moment scaling, metre/millimetre and S/m mistakes.
Nearest-triangle source depth, radial distance and tissue compartment are distinct
quantities. The per-source tables use the actual nearest inner-interface distance.

The original four deep positions and cap exactly reproduce M27's six discrepancies
before any adapter alteration. Changing the sensor layout and adding superficial
sources changes the estimand: the new 60-position aggregate is not a corrected
version of the old four-position metric. Original and subset results are retained
side by side. Gauge-independent primary comparisons use identical average
reference; fixed-reference differences do not select a preferred result.

Head5 is a heldout diagnostic treatment replicate in the frozen design. Its M27
geometry and historical baseline were already known; it is not an unseen anatomy
or an external population sample. No treatment was selected from head0 outcomes.
