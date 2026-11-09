# Prespecified decoding protocol — Milestone 5

Written before any decoding model experiment. Subjects 1–35 are development
data, previously inspected for exploratory EEG effects. Reserve 36–65 without
accessing their EDFs, features or outcomes until development evaluation, code
verification and final model-selection rules are frozen. The initial sealed
configuration is configs/decoding.yaml. A separately sealed decoding-frozen.yaml
must record final development-only choices, exact code/dependency identity and
input hashes before any held-out access. No model or rule is chosen using the
held-out cohort. Development findings are exploratory; the prospective evaluation
is conditional on this documented freeze and the nonrandom cohort selection.

## Data, preprocessing and eligibility

Binary T1=0 left-hand imagery, T2=1 right-hand imagery; right is the positive
class. Use runs 4/8/12 and validated half-open [1,3) seconds after cue. Continuous
1–40 Hz order-4 Butterworth prototype, zero phase, average reference over all
validated EEG channels. Fixed decoding order: FC3, FCz, FC4, C3, Cz, C4, CP3,
CPz, CP4. No ICA, interpolation, resampling, condition-average normalization or
subject-specific centering. Marked bad channels, unavailable channel identities,
inconsistent sampling/reference or insufficient contained context reject the
record with an explicit reason. No class-dependent exclusion or outside list.
Use existing 300 µV trial peak-to-peak, 150 µV absolute excursion and 0.05 µV
flat-SD thresholds on the fixed analysis channels, plus existing containment and
filter guards. Preserve every proposal, including rejected trials. For burst
features additionally require a contained [0,4) context; the common retained
trial set is used by all models for matched comparisons. Each event supplies
exactly one [1,3) window. Raw EDFs and boundaries remain unchanged.

## Representations and models

Nine models, all prespecified and always reported: C3/C4 mu log-power logistic
regression; C3/C4 mu+beta log-power shrinkage LDA; nine-channel mu+beta log-power
logistic regression; nine-channel mu/beta burst logistic regression; MNE CSP +
shrinkage LDA; vectorized regularized covariance + shrinkage LDA; Euclidean
minimum-distance-to-class-mean; affine-invariant Riemannian MDM; and Riemannian
tangent-space logistic regression. Fixed voltage scaling to µV for matrix
conditioning is a units conversion, not fitted normalization. Empirical, fixed
shrinkage, OAS and Ledoit-Wolf covariance APIs will be validated; primary matrix
models use per-trial OAS plus a trace-relative 1e-6 eigenvalue floor, without
trace normalization. Record pre/post eigenvalues, condition numbers and ranks.
Average reference does not guarantee full rank. No anatomical source claim.

NeuroDSP supplies Welch PSD and dual-threshold burst detection. Calculate
fold-independent PSD and band-filtered/Hilbert context once per trial. Burst
thresholds are fitted on training-only analysis-window amplitudes (per-channel,
per-band pooled median, low=1×, high=2×); apply fixed learned voltage thresholds
to each trial's own context without test-derived renormalization. Features are
occupancy, mean burst amplitude (zero if none), observed burst-onset rate and
mean complete burst duration (zero if none). Edge-crossing fragments do not
supply complete durations. A three-cycle filter and one-second context margins
are explicit finite-window approximations, not continuous M3 burst estimands.
Feature scaling, CSP, class covariance means, tangent references and supervised
selection fit only permitted training partitions. Test covariance is per-trial,
with no population mean or reference adaptation from test participants.

## Splits, tuning and adaptation

Within-subject: train on two runs, test on the third, all three held-out runs.
Use fixed C=1, CSP four components/0.1 shrinkage; two training runs do not justify
trial-random tuning. Cross-subject: deterministic five-fold GroupKFold by subject,
with three-fold subject GroupKFold inside each training fold. Logistic C in
[0.1,1], CSP components [2,4] × covariance shrinkage [0.1,0.3]; all other settings
fixed. Use mean subject balanced accuracy for inner selection (equal subjects,
not pooled trial weighting). Deterministic ties select the first search entry.
Refit a fresh pipeline only on outer training data. Reject pre-fitted estimator
objects and raw event/window overlap. Save every membership and candidate score.
No random trial CV, external feature tables without provenance, or outer-test
selection API. Cache only trial-local, label-independent arrays; never cache a
fitted supervised transform without exact training-partition identity.

Adaptation is a separate exploratory mode for multiband/tangent logistic models.
Reuse the source-subject outer partitions; source-only inner choices are fixed.
For each new subject, add exactly 0/4/8 labeled accepted run-4 trials, selecting
chronologically the first k/2 in each class. Refit the source pipeline on source
trials plus calibration trials; evaluate only runs 8/12, excluding all run-4
trials. If insufficient calibration class support exists, record that cell as
failed rather than reducing k. No target test statistics, target test fitting,
additional adaptation search or rule selection. This pooling rule tests a simple
limited-label baseline, not optimal domain adaptation.

For prospective evaluation, choose each model's hyperparameters by the same
subject-balanced inner search over development subjects only. Seal all choices
and training inputs first, then explicitly fetch/access 36–65. Cross-subject
models train on all development subjects and test each held-out participant.
Within-held-out and labeled-adaptation modes retain the same fixed procedures;
within-held-out fitting is explicitly subject-specific and cannot be described
as zero-shot transfer. Keep those modes separate. No held-out winner selection.

## Metrics, nulls, comparisons and reporting

Primary metric balanced accuracy. Also accuracy, confusion counts, sensitivity
(right), specificity (left), ROC-AUC for continuous scores, class counts, and
Brier/log loss plus reliability-bin tables for genuine model probabilities.
MDM distance-softmax scores are labeled uncalibrated similarities; do not call
them calibrated probabilities. Subject/run metrics remain visible. Summarize
uncertainty over subject mean scores, never over trial counts. Trial probability
calibration curves are descriptive; no claimed independent-trial confidence bands.

Always include a training-prior dummy baseline. Synthetic null trials have labels
independent of signals. Development cross-subject nulls for multiband/tangent
use 19 independent seeded permutations of labels within subject/run; repeat
nested tuning and all fits, not just score shuffling. This conditional null
assumes exchangeability within runs and may be imperfect for temporally correlated
trials. Its p-value resolution is 1/20 and it is exploratory. No expensive null
suite in standard CI. Main inference uses paired subject performance differences
for tangent−multiband, Riemannian−Euclidean MDM, CSP−multiband. Report t/percentile
intervals, sign-flip tests assuming symmetric independent subject contrasts, Holm
family of three per evaluation mode, and leave-one-subject-out influence. Missing
comparisons stay in the planned family. Cross-validation training sets overlap,
so these subject summaries are descriptive approximations, not guaranteed exact
independent error inference. Prospective subjects are independent evaluation
units conditional on the fixed development training set.

Preserve failed folds, numerical warnings, trial/class distributions, fit times,
CPU, peak RSS, seeds, source/code/dependency hashes, and all fold memberships.
Never promote a method based on prospective outcomes. Record a development-only
selection receipt before held-out access; no automatic held-out download during
development. Generate sensor-pattern, eigenvalue/conditioning, geometry, confusion,
score distribution, adaptation and synthetic figures from saved numerical tables.
No deep neural network, source reconstruction, MRI or Milestone 6 work.
