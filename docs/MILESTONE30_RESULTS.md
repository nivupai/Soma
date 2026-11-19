# Milestone 30: independent mesh replication and source-grid convergence

M30 branches from M29 `88fcda2f2d4fd4f215294fac966fa180a6594df9`, with dependent
PRs #14 and #13 still unmerged. The physical design was committed at `2c4a369`
before final outcomes. Design SHA-256 is
`19d681211937bdba3b55c54eade56920d98593dcb365ab0047eda75411c5e3a9`;
M19 protocol fingerprint is
`61360de2076b3e4e01853358b3a66bcf69aced771fb7ad7e11f4b1cfff8cc46b`.
Local sealing is not external preregistration. No final outcome changed the
mesh schedule, candidate grids, regularization or acceptance targets.

## Independent mesh and physical replication

Official Gmsh 4.15.2 generates native Delaunay tetrahedra; it does not call Soma's
radial mesher. FEM remains scikit-fem 12.0.2 P1 full subtraction. The BEM reference
is OpenMEEG 2.6.0. This isolates meshing independence while explicitly retaining
a shared FEM formulation. Gmsh is optional and external; its GPL v2-or-later and
specific linking exception are documented in
[the mesher review](INDEPENDENT_MESH_REPLICATION.md). No upstream code/binary is
vendored or relicensed.

Six original independent M27 head generators, two per fixed shape family, retain
brain/CSF/skull/scalp conductivities .33/1/.004/.33 S/m, insulating exterior,
MRI/RAS metres, 32 common nodal electrodes and the same average reference. Native
Gmsh volume facets preserve their supplied surface coordinates/connectivity
exactly in the audited configurations; material-volume sums and interface
adjacency are independently checked. Standard forward mesh sizes span roughly
1,017–1,068 / 4,990–5,758 / 23,498–24,531 tetrahedra across the three levels.
All accepted meshes have positive elements; the minimum mean ratio is .02273.
Native minSICN and independent mean-ratio measurements are retained separately.

The alternative surface path rotates the angular sampling, includes the 32
physical electrode directions, creates a new hull, and maps the same smooth
four-boundary target. These boundaries are not identical to the standard BEM
approximation. Sampled maximum mismatch against the finest standard polyhedron
is 1.296–1.651 mm at level2 and .345–.423 mm at level3. Distances sample vertices
and facet centroids; they are not certified continuous Hausdorff distances.

| Finest forward comparison | Unscaled relative field difference |
| --- | ---: |
| Gmsh FEM / standard BEM, identical interfaces | .314–.527% |
| Gmsh FEM / BEM, matched alternative interfaces | .520–1.318% |
| Alternative Gmsh FEM / separately discretized standard BEM | .424–1.137% |
| Alternative BEM / standard BEM, geometry perturbation | .269–.347% |

All six finest matched comparisons pass the frozen 10% engineering target.
The original M29 radial result (.304–.607%) is preserved and is not relabeled as
a new computation. Strong agreement survives independent volume meshing and
an alternative surface representation, within this bounded synthetic model set.
It does not prove absolute nonspherical accuracy or human anatomical validity.
Shared electrode vertices and physical target definitions remain shared inputs.

The differing-boundary comparison includes geometry error. A vector decomposition
uses a common standard-BEM denominator: the matched alternative discretization
residual plus the BEM-only geometry perturbation equals the combined field delta.
Those vectors may reinforce or cancel. Their scalar norms cannot be uniquely
added or assigned to one cause. All components, correlations, physical RMS voltage,
orientation, depth, conditioning and unscaled fields remain in the public tables.

## Analytical reference and convergence

| Gmsh FEM reference | Level1 | Level2 | Level3 |
| --- | ---: | ---: | ---: |
| Homogeneous sphere, standard facets | retained compatibility failure | 2.467% | .592% |
| Four-layer sphere, standard facets | 14.245% | 3.652% | 1.043% |

Alternative finest facets reach .612% homogeneous and 1.229% layered error.
The applicable independent homogeneous and harmonic transmission references are
used, not OpenMEEG as the sole truth. The exploratory homogeneous pilot passed
before the full design was frozen. The full coarse homogeneous case exceeds the
fixed RHS compatibility limit and stays failed; its tolerance is not relaxed.

Standard same-solver level1→2 changes range 10.68–13.82%, and level2→3 changes
2.60–2.84%. Alternative level2→3 changes are 2.68–2.80%. These are repeated
computations on finite meshes, not an asymptotic-order proof. Algebraic residuals
remain distinct from field/geometry/source-discretization convergence; the largest
recorded FEM relative residual is approximately 2.34e-13.

## Source-grid convergence: lower bounds improve, regularized errors do not uniformly improve

The legacy 12-candidate grid and frozen 33/147/341-candidate Cartesian grids all
receive the same off-grid source generators, moments and noise. Actual source
positions are never added to the candidates. The new spacings are 30/20/15 mm;
the grids are not nested. User regularization parameters and a fixed per-head
spectral scale are retained across all grids/models. MNE's intrinsic source-covariance
normalization is explicitly acknowledged.

At .05 µV noise, averaging six heads and 12 independent sources per head:

| Candidates | Mean nearest distance (mm) | Tikhonov FEM / BEM peak error (mm) | MNE FEM / BEM (mm) | dSPM FEM / BEM (mm) |
| --- | ---: | ---: | ---: | ---: |
| 12 legacy | 53.441 | 55.506 / 55.622 | 56.031 / 56.219 | 56.569 / 56.617 |
| 33 | 14.831 | 24.347 / 24.670 | 24.536 / 24.677 | 46.290 / 46.566 |
| 147 | 9.814 | 32.934 / 34.142 | 26.587 / 26.611 | 43.048 / 43.166 |
| 341 | 7.479 | 34.613 / 35.658 | 26.985 / 26.291 | 42.046 / 42.108 |

The nearest-distance improvement does not establish regularized inverse convergence.
At 341 candidates, mean excess error above the geometric lower bound is
27.13/28.18 mm Tikhonov, 19.51/18.81 mm MNE and 34.57/34.63 mm dSPM.
There is no clean transition to generally solver-limited peak accuracy over this
finite hierarchy. Model effects become more visible but remain much smaller than
absolute error; inversion, priors, source orientation and finite geometry remain
important. No grid or hyperparameter is selected afterward to improve the headline.

For 341 candidates at .05 µV, paired BEM−FEM peak-error differences are:
Tikhonov +1.045 mm [.106, 2.022], MNE −.694 mm [−1.729, −.018], and
dSPM +.062 mm [−.060, .263]. These are conditional, uncalibrated hierarchical
simulation intervals, not significance declarations or human confidence intervals.
Direction depends on inverse method; there is no universal solver-superiority claim.
Full/noiseless/high-noise results, dispersion, physical per-candidate peak bias,
paired peak displacements, resolution matrices' hashes/diagonals and point-spread
responses are preserved. dSPM amplitudes are never treated as physical dipole currents.

The alternative-truth sensitivity is limited to prescribed head0 and heldout head5,
finest grid and .05 µV. Head0 peak changes are zero in the tested methods/models;
head5 mean changes are −.112 mm for BEM/MNE inverse and +.037 mm for BEM/Tikhonov,
with the remaining mean peak changes zero. This is coarse peak insensitivity,
not identical fields or general anatomical robustness. Per-source changes and
all raw sensitivity reconstructions remain available; no pooled six-head interval
is fabricated from two heads.

## Coverage, uncertainty, resources and reproducibility

There are 85 completed configuration rows and one retained coarse homogeneous
failure. They comprise 79 newly evaluated field arrays and 12 reused/truncated
legacy grid operators, with six matched alternative-BEM controls nested in forward
rows. These are not 85 independent heads. There are 29,376 primary inverse rows,
1,152 geometry-truth sensitivity rows and no failed/missing inverse evaluations.
Independent units are six head generators and 72 nested off-grid source draws.
Sensor channels, XYZ components, candidate cells and noise repeats are not subjects.

Source/noise averaging and family-stratified head-then-source bootstrap summaries
are supplied separately for forward comparisons, refinement, nearest-grid distance,
localization and paired model effects. Geometry summaries resample heads only.
Resolution comparisons require the same ordered grid and compatible units; dense
matrices stay local with public hashes, summaries, diagonals and selected PSFs.
The finest Gmsh truth shares an FEM formulation with one inverse model, leaving
correlated validation despite distinct meshes and off-grid source locations.

The full frozen run takes 1,029.276 seconds. Maximum measured field-solver child
RSS is 496.078 MiB for FEM and 1,203.984 MiB for matched alternative BEM, including
imports. Separately labeled isolated post-run kernel/full-resolution benchmarks
on head0/head5 take .065–.167 s with 287–332 MiB peak RSS. Those timings do not
replace total experiment runtime or measure all field assembly costs.

`experiments/milestone30` contains physical operators, mesh/label and deviation
maps, field/grid/uncertainty/PSF/resolution data, uniquely named executed source
snapshots, native M17/M19 receipts and 19 scientific figures. Inputs are synthetic;
there is no participant MRI/EEG, licensed anatomical asset or measured phantom.
All M28/M29 artifacts and 46 M24 archive hashes remain unchanged.

[Verification](MILESTONE30_VERIFICATION.md) reports actual software and package
checks. The dependent PR remains blocked while the required upstream npm audit
fails; no merge or postmerge CI is claimed. Proposed M31: independently test
source-density/prior normalization and inverse regularization against denser
prespecified grids, plus a second FEM formulation or smooth-boundary reference.
M31 has not started.
