# Whole-model mesh convergence — Milestone 27

The finest level-3 four-interface operator is a numerical reference, not exact
physical ground truth. Truth sources are independently sampled off-grid and
use a distinct finer forward calculation; no inverse kernel generates test data.
Sources, conductivities and head identity stay fixed when baseline meshes change.
Sensors are projected onto each discrete scalp, so this is whole-model geometry,
sensor discretization and BEM convergence, not isolated quadrature convergence.

| Head / family | L0 relative error | L1 | L2 | Rates log2(error ratio), L0→L1 / L1→L2 |
| --- | ---: | ---: | ---: | ---: |
| 0 prolate | 0.668496 | 0.108979 | 0.022798 | 2.617 / 2.257 |
| 1 prolate | 0.664304 | 0.108227 | 0.022736 | 2.618 / 2.251 |
| 2 oblate | 0.818053 | 0.107008 | 0.021937 | 2.934 / 2.286 |
| 3 oblate | 0.778638 | 0.106655 | 0.022032 | 2.868 / 2.275 |
| 4 asymmetric | 0.726337 | 0.106885 | 0.021807 | 2.765 / 2.293 |
| 5 asymmetric | 0.719986 | 0.106360 | 0.021927 | 2.759 / 2.278 |

All six satisfy the precommitted finest-comparator error ≤5% and both successive
error ratios ≤0.8. Rates use subdivision level, not a proved PDE asymptotic order.
A finite finest reference can share systematic bias with all estimated meshes.
No extrapolated zero-mesh-size limit or independent four-layer certification is
claimed. Exact public `head-N/convergence.json` values take precedence over rounding.

`field-attribution.csv` separates total field difference from the finest baseline
and perturbation mismatch at fixed level 2. Conductivity, geometry, electrode
and registration cases are paired within head. The new spherical control also
changes sensor mapping and numerical formulation; its field difference cannot
be attributed solely to shape. Peak-distance improvements alone do not certify
a better conductor. The frozen three-layer independent-control disagreement
remains a separate failed gate.

Fine four-layer solves used 6408 unknowns, approximately 16 s assembly/solve and
at most 1135.84 MiB child-process peak RSS. The dense storage bound is an estimate;
RSS includes imports and is not an allocation-only measurement. The whole primary
study including geometry checks took 349.041 s, below its 1800 s budget. Public
cost figures distinguish child solve time from controller time. No case was
silently omitted for computational cost.

The newly generated spherical operator differs from each finest nonspherical
operator by 2.394–5.742% relative Frobenius norm. This descriptive contrast
combines shape, scalp sensor mapping and formulation differences. Fixed-level
perturbation fields and total discretization errors are separate columns in the
attribution table; they must not be interpreted as independently identified
human anatomical error components.
