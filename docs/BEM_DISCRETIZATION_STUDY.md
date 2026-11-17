# Independent BEM discretization study — M28

The fixed sensor nodes remain identical at all levels. Only triangulated surface
resolution and corresponding numerical operators change. This removes M27's
mesh-dependent sensor projection from the primary schedule, but the polyhedral
approximation to the smooth geometry still changes with refinement.

| Quantity | Level 1, 80 triangles/interface | Level 2, 320 | Level 3, 1280 |
| --- | ---: | ---: | ---: |
| Exact homogeneous error, OpenMEEG, 6 locations XYZ | 23.838% | 5.765% | 1.412% |
| Exact homogeneous error, MNE, same locations | 4.058% | 1.561% | .472% |
| Homogeneous one-interface OpenMEEG error | 25.751% | 6.192% | 1.501% |
| Layered semi-analytical difference, OpenMEEG, 5 off-centre locations | 16.321% | 3.980% | 1.028% |
| Layered semi-analytical difference, MNE | 17.302% | 17.043% | 9.063% |
| Six nonspherical paired field differences, all 60 locations/head | 27.619–28.843% | 26.334–27.136% | 11.709–12.208% |

The homogeneous reference independently differentiates regular solid harmonics
for an insulating sphere. With t=source/R and u=sensor/R, H0=1, H1=u·t and
H(n+1)=((2n+1)(u·t)Hn−n(t·t)H(n−1))/(n+1). Surface dipole fields are
sum((2n+1)/n ∇t Hn)/(4πσR²). The n=0 gauge is omitted. At the centre this reduces
to 3u/(4πσR²), independently checking units and sign. The 64/128-term relative
difference is 7.16e-14. Independent finite differences of SciPy Legendre
polynomials test the gradient recurrence. The 2% finest homogeneous aggregate
gate passes for both solvers; it is not a per-source maximum guarantee.

MNE's public EEG API rejects one-interface BEM, so three equal-conductivity
interfaces represent the same homogeneous continuous problem. OpenMEEG's additional
one-interface control distinguishes artificial internal discretizations. The
layered reference uses MNE's approximate spherical formulation with equal first
two conductivities, not an exact independently implemented layered series. It
shares the MNE codebase and cannot alone establish a unique absolute error bound
for collocation. The independent homogeneous limit is therefore reported separately.

Within-solver successive differences shrink: OpenMEEG .1212–.1222 to .0303–.0308;
MNE .2013–.2083 to .0920–.0946. Both pass the prespecified ratio .8 criterion.
This three-grid sequence is not proof of a theoretical asymptotic order or a
common limiting solution. Cross-refinement tables compare every 3×3 solver-level
combination; their different discrete geometries are labeled explicitly.

Single-interface refinement is not uniformly beneficial: refining the inner
interface increases the paired gap norm by about 18%, middle refinement reduces
it about 7%, and outer refinement about 12%, in both head0 and heldout head5.
This supports coupled interface/formulation discretization effects rather than
a universal one-surface fix. Further refinement and an independent layered
analytical reference are needed to identify the remaining limit. The unchanged
10% independent agreement gate still fails for all six primary finest comparisons.

`mesh-spacing.csv` reports physical surface area and characteristic spacing
sqrt(area/triangle count) for every interface/head/level. A separate log-log plot
relates physical field differences to scalp spacing; three levels do not establish
a theoretical convergence order.
