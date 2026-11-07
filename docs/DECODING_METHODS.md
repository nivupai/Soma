# Neural decoding methodology

## Trial and model boundaries

`TrialDataset` holds X=(trial,channel,sample), integer binary y, aligned context,
channel order, sampling rate and cue intervals. Every retained trial has subject,
run, recording, event and trial identifiers, half-open raw sample bounds, QC and
preprocessing fingerprint. Missing provenance, duplicate windows, mixed references
and incompatible concatenations fail. Each event contributes one analysis window.
IDs and labels live outside numeric model inputs. Every real-file QC proposal is
preserved in the checksummed trial cache; coverage reports retain file failures.
The common [0,4) context requirement makes comparisons use matched retained trials.

`FeatureBank` calculates NeuroDSP Welch log-bandpowers, local band-filtered contexts
and Hilbert amplitude, and per-trial OAS matrices. These contain no class- or
population-derived statistics. OAS covariance estimates are reused across models
and folds; a regression test establishes equality with direct raw-tensor pipelines.
Burst low/high voltage thresholds are pooled training-only medians times 1/2.
The existing NeuroDSP adapter cancels its internal per-input median normalization,
so application uses the fixed learned voltage thresholds rather than refitting a
test reference. No-burst amplitude/duration are explicitly zero. Complete-duration
features omit boundary-crossing events; onset rates count actual context onsets.
Finite-context filtering differs from M3 continuous burst definitions.

All model fitting uses new sklearn Pipelines. Scaling is training-only. CSP and
all supervised structure fit after splitting. Tangent references and class means
use only training trials. `tsupdate=False` forbids test-reference updates. No
subject centering, test-condition normalization, global PCA, or test-driven
feature selection is performed. Trial covariance time-centering is part of each
trial's covariance definition, not estimation of a held-out participant's mean.

## CSP and covariance

For class covariance matrices S_L and S_R, CSP solves the generalized eigenvalue
problem S_L w = lambda (S_L+S_R) w. Directions with different class variances
produce discriminative log-power features. MNE average_power logs the temporal
mean squared spatial-component signal; this is variance when that signal has
zero mean. MNE supplies the validated algorithm,
mutual-information component order, rank estimation and shrinkage. The code
checks measured training rank against requested components. Pattern/filter signs
and component orders are ambiguous across folds; stability uses absolute cosine
similarity with optimal component matching, never naïve pattern averaging.
Topographies show one training fit with template sensors and arbitrary pattern
units. They describe sensor-space transforms, not localized anatomical sources.

With centered trial samples Z, empirical covariance is Z Z^T / T (ML normalization).
Fixed shrinkage is (1−rho)S+rho tr(S)/p I. OAS/Ledoit-Wolf estimate rho per trial
with sklearn. Their independent-sample/Gaussian risk assumptions do not hold
exactly for autocorrelated EEG; they are used here as explicit regularizers,
not a claim of statistically optimal shrinkage for these signals. Convert fixed
V→µV units before matrix operations. Trace normalization is optional and changes
the representation by discarding global power; the primary uses no trace normalization.

Measure symmetry, rank, eigenvalues and condition number. Floor eigenvalues at
1e−6 tr(S)/p for primary matrix models. An all-zero-energy matrix fails; no
arbitrary energy is invented. A floor can regularize a lost average-reference
mode but cannot recover physiological information in it. Average referencing over
64 sensors followed by a nine-channel subset need not have rank eight; rank is
measured rather than assumed. Empirical, fixed shrinkage, OAS and Ledoit-Wolf APIs
have scale/permutation tests. Covariance vectorization uses sqrt(2) off-diagonal
weights to preserve the Frobenius inner product.

## SPD geometry

For SPD A and B, affine-invariant distance is
`||log(A^(-1/2) B A^(-1/2))||_F`. pyRiemann implements this and the intrinsic mean
minimizing squared distances. The Euclidean mean minimizes squared Frobenius
distances and is a different estimator. For diag(1,9) and diag(9,1), the intrinsic
mean is 3I while the Euclidean mean is 5I. Matrix logarithms/exponentials operate
on positive eigenvalues. Singular matrices require an explicitly regularized
representation; symmetry alone does not imply SPD.

Tangent features use `log(C_ref^(-1/2) C C_ref^(-1/2))`, with C_ref fitted from
training matrices and sqrt(2)-weighted symmetric vectorization. Classifier scaling
and logistic fitting follow in the training pipeline. The descriptive 2D plot
shows the first two coordinates of the first outer test fold under its training
reference; it is not a global embedding or a source map. MDM compares distance
to training class means. Its signed distance margin supplies ROC-AUC; it is not
presented as a calibrated probability. Logistic/LDA probabilities support Brier,
log loss and descriptive reliability bins.

Distance and intrinsic-mean congruence invariance concern already computed SPD
matrices. OAS shrinkage to I and eigenvalue floors are not generally equivariant
to every invertible channel transform. Do not extend the geometry theorem to a
full re-estimated/shrunk pipeline. Channel permutations and uniform scaling have
separate valid covariance tests; precomputed MDM congruence predictions are tested.

## Generalization, selection and uncertainty

Within-subject fitting uses two runs and the third for testing; missing runs
produce failed planned cells instead of switching to one-run training. Cross-
subject outer GroupKFold holds participants out entirely. Inner GroupKFold sees
only outer training participants. Candidate scoring averages subject balanced
accuracy, not trial scores weighted by how many windows survive. Ties select the
first prespecified grid entry. All memberships, candidate scores, warnings,
training-label checksums and fit timings are stored. Prefitted external models
are rejected; there is no API accepting an outer test score to choose parameters.

The subject-level primary summary averages observed run balanced accuracies,
then equally averages subjects. Paired comparisons first match subject/run cells,
then average paired run differences within subjects. No inference treats windows
as independent people. Nominal t and percentile intervals, symmetric-null sign
flips and planned-family Holm adjustments are descriptive for overlapping CV
training sets. Adaptation comparisons retain the three planned model comparisons
at each calibration count, with absent comparisons conservatively p=1; their
exploratory tangent contrast is thus adjusted by a factor of three at each count.
These are not independent learning-curve tests or a selected optimal calibration k.

Limited adaptation pools a fixed balanced 0/4/8 labeled run-4 subset with source
training data, retaining source-only selected hyperparameters. Runs 8/12 alone
are evaluated. This simple small-weight pooling baseline need not improve
performance; no optimal transfer-learning claim is made. Insufficient class
support creates a failed calibration cell rather than a reduced trial count.

Dummy priors are training-only. Independent-label synthetic data and real within-
subject/run label permutations test null behavior. Real permutations repeat
nested tuning, not only score labels. Nineteen permutations imply a minimum
Monte Carlo p-value of 0.05; within-run exchangeability may fail under temporal
correlation. Report coarse null evidence, not finely resolved p-values.

Prospective zero-shot transfer must use development-selected frozen settings.
The same held-out participants can also have separately labeled within-subject
and adaptation experiments under the fixed rules; those are not zero-shot results.
Never select a winner using held-out scores. Repeating the deterministic held-out
workflow is reproduction of the same sample, not another prospective experiment.

References: [MNE CSP](https://mne.tools/stable/generated/mne.decoding.CSP.html),
[pyRiemann](https://pyriemann.readthedocs.io/en/latest/api.html),
[sklearn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).
Installed APIs were inspected directly (MNE 1.13.2, pyRiemann 0.12, sklearn 1.9.1).

## Supplemental preprocessing diagnostic

A separately sealed `configs/decoding-sensitivity.yaml` specifies an explicitly
post-hoc development-only CSP diagnostic after the main development results were
seen. It compares average/acquisition/Fz-Pz references and 8–30 versus 1–40 Hz,
with fixed four-component/0.1-regularized CSP and the identical retained-trial
intersection across variants. Both run-held-out and subject-held-out splits are
reused; there is no tuning or winner selection. This diagnostic does not change
the primary preprocessing or prospective model rules. Its script hash, config,
trial coverage, memberships and fits are preserved. It is exploratory, not an
additional confirmatory analysis. Run it with:

`python experiments/decoding_sensitivity.py --output reports/m5-decoding-sensitivity`

Adaptation's zero-label curve uses only runs 8/12, so its baseline is not directly
identical to the main zero-shot score over runs 4/8/12. Interpret changes across
k on the same adaptation evaluation cells, rather than comparing unmatched runs.
