# Functional modeling and interpretation policy

A FunctionalRun requires explicit subject/session/task/run/space, 4D finite BOLD,
TR seconds, coded matching geometry, mm/sec header units, same-grid binary mask,
aligned confounds and preprocessing provenance. Validated status requires external
evidence; declaring it is not a Soma preprocessing validation. Raw educational
fits require explicit opt-in. No SDK interface downloads or silently preprocesses.

The existing Nilearn engine estimates `Y=X beta+epsilon`. ModelConfig records HRF,
drift, nuisance terms, noise model and smoothing FWHM in mm. A named Contrast maps
actual design names to coefficients c; the effect is cᵀ beta. Contrast dimensions,
rank and estimability are checked. Effect units are input BOLD units per modeled
regressor unit. Standard errors depend on the modeled noise covariance. Signed t
and Gaussian-equivalent z maps and two-sided p values remain experimental outside
the narrowly calibrated synthetic class. AR estimation, misspecified HRFs, temporal
noise, smoothing, confounds and spatial multiplicity all affect uncertainty.

`fmri.contrast` is the original guarded function. Human and feasible-AR outputs
remain descriptive. `InferencePolicy(mode="confirmatory")` rejects unsupported
human inputs. The only supported synthetic confirmation class remains the exact
Milestone14.1 contract; this SDK release expands no calibration claim. Merely
assigning SDK result metadata cannot authorize confirmation. Stored rejection maps
are not clinical findings. Do not interpret synthetic recovery as human validation.

ROI label ontologies and explicit transform chains must align with effect maps.
ROI summaries report coverage and partial-volume warnings; ROI inferential standard
errors remain unavailable because spatial covariance is not modeled. Fixed effects
require compatible distinct runs of the same subject/task/space and explicit effect
scale. They do not provide population random-effects inference.

Execute `python -m examples.fmri_contrast` for an independent-HRF synthetic model.
It checks opposite signed effects and descriptive policy, not a human detection rate.
