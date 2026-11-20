# M31 regularization calibration

All rules were frozen in commit 44adeed before M31 final outcomes. Historical
M30 outcomes were already known. Local sealing is not external preregistration.

For B = A R Aᵀ, the sensor shrinkage eigenvalues are b/(b+α). The effective degrees
of freedom are their sum; regularized conditioning is (bmax+α)/(bmin+α). Residuals
are evaluated in the retained, whitened sensor subspace. Source localization is
not the criterion used to tune α.

A: Historical Tikhonov uses α = 0.001·(s₀ j₀/σ₀)², where s₀ is each head's original
finest legacy-12 forward spectral norm and σ₀=0.05 µV. MNE/dSPM use α=1/9 after
intrinsic trace normalization. These are the original M30 settings, not a claim
that equal user parameters yield equal effective regularization on different grids.

B: Spectral normalization holds α/bmax = 0.001 for Tikhonov and 1/9 for MNE/dSPM.
Thus the best-resolved sensor eigenmode has fixed shrinkage, while the remaining
spectrum and EDF can still change. This is an explicit numerical scale control,
not a physiological variance estimate. Global rescaling of R cancels in this
policy; Tikhonov unweighted and total-variance controls are identical here.

C: Independent-repeat prediction minimizes mean squared whitened sensor prediction
error from noisy repeat 0 to independently noisy repeat 1, using calibration
sources 0–5 only. The logarithmic sweep is 17 values α_A·10^t, t=−4,−3.5,…,4.
Ties choose the first/smallest value. Selection is separate for each head, grid,
prior, method and noise level. No final test source location, orientation,
localization error or clean field enters selection. The clean field is used only
for subsequent simulation performance evaluation. This is sensor-space tuning,
not independent-head or anatomical validation.

All noiseless tuning configurations select a boundary: finite lower-bound optima
remain reported, with no sweep extension or post-outcome rescue. Boundary fractions
at 0.05/0.15 µV are 11.59%/2.90%, including the two-head BEM subset. These are
limitations of the frozen diagnostic sweep. No final test error selects a method,
prior, grid or policy for a validation headline.

`regularization-curves.csv` contains all 21,114 prespecified calibration losses.
`operators.csv` retains α, α/bmax, EDF, covariance traces, conditioning, resolution
diagonals/trace, PSF widths, runtime and RSS for all configurations. The noise
covariance is deliberately fixed across actual noise levels; extending this to
heteroscedastic EEG or data-estimated covariance requires separate validation.
