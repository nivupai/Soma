# Prospective EEG model release — v0.24.0

This is a newly trained release, **not the original M22 fitted state**. M22 preserved
predictions, selected hyperparameters, partitions and partial fit audits. It did not
preserve complete classifier coefficients/intercepts, scaler scales or MDM class
means. Those historical outputs remain unchanged; matching predictions cannot
recover or authenticate their original weights.

The new M19 seal is `configs/eeg-model-training-v24.json`. Its protocol fingerprint
is `1728ec7911c62612f4c4735267b5196d881d6e40ab069028c26ee0a9b5a83fcb`.
The local UTC seal time, source inventory fingerprint, code hash and permission
identity are in `experiments/milestone24/freeze.json`. This is a local seal, not
external preregistration. Prospective means state was archived before future
external evaluation. The study design and source outcomes were historically reused.

Training uses the existing cached EEGBCI v1.0.0 source-role subjects 1–35 and imagery
runs 4, 8 and 12. Only these 105 source recordings are opened for the workflow; their
hashes match the corresponding M22 inputs. No evaluation-role subjects are loaded
for training or parameter selection. The existing content-bound M20 policy supports
local methods analysis and aggregate export under the cached PhysioNet ODC-By1.0
notice. This does not attest individual consent or authorize redistribution of weights.

The fixed protocol retains M22 preprocessing/QC: 160Hz, nine ordered motor channels,
average reference over all EEG before ROI selection, fourth-order zero-phase1–40Hz
filtering, cue-relative1–3s epochs, and the established rejection thresholds. Events
T1/T2 map to left/right0/1. Natural-log mu8–13Hz and beta13–30Hz powers use Welch
160sample windows and80sample overlap. Trial-local OAS covariance uses microvolt
scaling, relative eigenvalue floor1e-6 and no trace normalization.

Parameters are fixed before this fit: band-power LR C=1; CSP4 components/reg0.1
followed by lsqr LDA/shrinkage auto; Riemannian MDM; tangent LR C=0.1; and a majority
reference with ties assigned class0. Seed22042 and float64 are fixed. No calibration,
new search, target adaptation or favorable sensitivity selection occurs.

All eligible source trials train the released models. A separate three-fold
GroupKFold by source participant repeats the relevant M22 source-selection procedure
with these already selected settings, without reselecting them. These source-fold
metrics describe the fitting procedure, not independent testing of the final all-source
weights. Historical selection on the same participants limits their interpretation.

The actual release contains35/35 subjects,105 recordings and1,441 retained trials.
Weights, probes, recording decisions, subject distributions and trial predictions
remain in ignored private storage. A separate review and authorization would be
needed before distributing any human-derived fitted state.
