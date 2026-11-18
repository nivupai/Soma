# Conditional inverse consequences of four-layer forward mismatch

Truth measurements use finest FEM off-grid fields and the original M27 arbitrary
signed 10 nA m moments. The inverse uses the 12 fixed grid probes at level 2, frozen
Tikhonov .001 and MNE/dSPM 1/9 regularization, with one finest FEM candidate spectral
norm per head shared by both model estimates. The grid is deliberately sparse;
nearest-grid error is retained. It is not an optimized localization benchmark.

Sources are distinct from candidate locations. Fine FEM truth and coarse FEM inverse
share a numerical method, so this avoids exact operator reuse but not all correlated
validation. Results cannot establish general physical solver superiority. No
hyperparameter is selected from the final errors.

Noise is sensor-average projected, 0/.05/.15 µV, with one noiseless and eight noisy
realizations per source and unchanged M27 RNG seeds 27042+10000+head. Each method
and solver receives exactly the same measurements. Outputs include peak error,
spatial dispersion, nearest-grid bound, energy outside20mm, resolution norm, and
physical peak bias for Tikhonov/MNE. dSPM is normalized and not a current estimate.

Noise/method/model repeats are averaged within source before paired hierarchical
summaries. The six heads and 12 off-grid sources per head are identified separately
from the total number of reconstruction rows. Actual numerical results and retained
failure counts are reported in `MILESTONE29_RESULTS.md`.
