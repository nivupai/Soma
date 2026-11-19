# Frozen inverse source-grid convergence

The M29 legacy12-candidate grid is retained. New grids are Cartesian axes over
[−60,60]mm at30/20/15mm spacing, restricted to radius≤65mm, yielding33/147/341
candidates. The schedule was frozen after containment/resource checks and before
localization outcomes. These grids are not nested and no monotone improvement is
assumed. Off-grid truth remains the12 independent M27 source draws per head;
integer grid cells are never inserted at truth locations. All points must lie in
brain tissue and a truth/candidate separation below1µm is rejected.

Primary measurements use standard finest Gmsh FEM; both inverse models use standard
level2 physical interfaces. The finer truth operator and independent source
locations avoid exact operator reuse, but shared FEM formulation remains a correlated
validation limitation. The 12-legacy-candidate finest Gmsh spectral norm is fixed
per head and shared across all grids/models. Tikhonov .001 and MNE/dSPM1/9 are not
retuned. MNE's intrinsic covariance normalization is preserved and may interact
with grid density; constant user parameters do not imply identical effective
priors as the number of source cells changes.

The same M29 random seed37042+head produces paired sensor-average noise at
0/.05/.15µV, with one noiseless and eight noisy draws. Every grid/model receives the
same physical measurement vector. Head0 and heldout head5 have a separately declared
alternative-geometry truth sensitivity at the finest candidate grid and .05µV.

Nearest-grid distance is a geometric lower bound for peak localization. Actual
error, excess above that bound, spatial dispersion, physical peak bias and full
resolution matrices are computed. dSPM amplitudes are normalized and not physical
current. Per-candidate peak current is not a grid-volume-adjusted current density
or total recovered moment; denser grids can redistribute amplitude. Local dense resolution matrices have reproducible hashes; public outputs
retain their summaries and same-grid paired comparisons, plus point-spread responses
to the nearest candidate to truth sources0/1/2. Matrix differences between differently
ordered or sized grids, or incompatible units, are rejected. Dense matrices remain
local to avoid publishing unnecessarily large binary artifacts; reproduction
recomputes them from public physical operators and frozen settings.

Noise repeats are averaged within source before family-stratified head-then-source
bootstrap summaries. Six heads and72 independent source draws are distinct from
the number of reconstruction rows, cells or XYZ components. Intervals have
uncalibrated conditional simulation coverage, not human-population coverage.
Resource scaling includes separately labeled post-run isolated inverse-kernel/full
resolution construction measurements on head0 and heldout head5, with imports
included in peak process RSS. No performance measurement is substituted for the
frozen experiment runtime.
