# M31 grid/prior stability

Original grids remain unchanged: legacy 12 and non-nested Cartesian 33/147/341
candidates. The new hierarchy is the cumulative union of 30 mm, 20 mm and 15 mm
Cartesian schedules, with 33/173/481 sites. Sites are lexicographically ordered
after 12-decimal coordinate serialization. Each parent site is present in its
child. These are nested candidate sets, not an exact nested finite-element basis;
Voronoi cells are reassigned on refinement. The original 33 and nested-33 sets
have identical geometry in different ordering, providing an arrangement control.

No true source is inserted in any grid. Original 72 sources and new independently
seeded 24 sources remain off-grid by at least 1 µm. All sites and cells share a
65 mm ball domain. Nearest-grid distance is a geometric lower bound on a peak
error, not a localization validation target. Excess error subtracts that bound.

Raw unweighted whitened covariance trace rises from 2.838×10⁵ to 4.376×10⁶ on the
nested hierarchy. Cell-volume weighting changes 1.035×10⁵ → 1.085×10⁵; total-prior
variance normalization changes 1.032×10⁵ → 1.092×10⁵. Values are six-head means in
the fixed whitened units. Cell-volume sensor covariance relative drift to the
finest nested grid is 3.198% then 0.335%; total normalization gives 3.725% then
0.604%. This supports bounded covariance stability, not universal source recovery.
MNE's intrinsic trace is fixed at sensor rank 31; covariance shape can still vary.

Historical unweighted Tikhonov mean α/bmax falls from 4.13×10⁻⁴ on nested-33 to
2.84×10⁻⁵ on nested-481. This is a measurable change in effective shrinkage.
Both arrangement and covariance spectrum contribute; candidate count alone does
not identify the cause. Spectral controls fix α/bmax but do not fix full resolution,
EDF, source covariance shape or point-spread width.

Moment-space resolution diagonals and traces use Kmoment G. PSF widths are RMS
energy distances from the nearest candidate to new held-out source 12, using the
three-orientation block response. Public `point-spread.csv` retains observed
spatial values for head 0, spectral policies, all grids/priors/methods, 0.05 µV.
No dense source matrices of different size/order are subtracted. Existing guards
reject such comparisons and incompatible units. Comparable sensor covariance
matrices use identical ordered electrodes. PSF widths do not consistently narrow
under grid refinement; no general inverse-convergence claim follows.

Noise draws are averaged per source before fixed-family head-then-source
resampling. Six heads and 60 test sources are not 90,720 independent participants.
Intervals are conditional simulation summaries with uncalibrated coverage. They
are not population or human-anatomical uncertainty estimates.
