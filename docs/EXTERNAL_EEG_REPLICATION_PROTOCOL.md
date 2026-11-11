# External EEG locally sealed protocol

The local M19 seal is `configs/external-eeg-v23.json`; its fingerprint, file hash,
seal hash and dated local evidence receipt are in `experiments/milestone23/freeze.json`.
This is not OSF registration or an independently trusted timestamp. The seal binds
the present missing-input inventory. Acquiring/changing files requires a new
explicit inventory-bound plan before classification; it cannot reuse this seal.

Primary executable design, if appropriate local evidence and original MAT inputs
are later supplied: separately labeled EXTERNAL_REFIT, source subjects1–5 and target
subjects6–9, both actual sessions. This is a four-target-subject generalization
estimate, not a nine-subject external test. Source-only training uses fixed M22
hyperparameters, with no inner search or test-outcome tuning. A separate session
plan can fit sessionT and testE for all nine participants; it evaluates session
transfer in known participants, not subject-disjoint transfer. It needs its own seal.

Original class order must be left/right/feet/tongue; map1→0,2→1 and exclude3/4.
Preserve actual participant/session/run identities. Original MAT files must have
25 channels,250Hz metadata, one-based integer trial starts and source artifact
flags. Calibration-only records with no events are not invented task runs; exactly
six actual task runs are required. NEMAR BIDS/GDF formats are explicitly unsupported
by this MAT adapter; no automatic downloader or mirror fallback exists.

Convert documented microvolts to volts, use existing average-reference/1–40Hz
fourth-order zero-phase preprocessing across22 EEG channels (exclude EOG), then
antialiased16/25 resampling and the nine ROI channels in fixed order. Cue-relative
[1,3)s maps to trial-relative[3,5)s,320 samples. Event boundaries round to the nearest
160Hz sample, at most half a sample error. Apply existing physical trial-QC metrics
and reject provided artifact flags; retain every decision. Both sessions and all
six runs need at least two accepted trials per class/run. Retain exclusions and
missing target rows; no substitutions or score-based removal. Context is epoch-only;
no burst/context model is added or claimed identical to M22 context containment.

Five existing methods are fixed: majority, power LR, CSP LDA, Riemannian MDM and
tangent LR. The primary outcome is equal-participant/session/run balanced accuracy.
No supervised adaptation or exploratory sensitivity grid is silently enabled.
Permission, model, reference, label, shape, session or input-identity failures cause
an explicit blocked/error result. Human execution is currently BLOCKED with zero
observed trials and no accuracy estimates. Fictional reference executions are
separately labeled and cannot clear a human permission or fidelity gate.

Human execution additionally requires the existing M21 evidence bundle: its
hash-checked reviewed document, dataset/version and protocol fingerprint must match
this plan, and its action/distribution scope must support analysis and aggregate
export. The M20 permission record alone is insufficient. Missing, changed, revoked
or mismatched evidence remains BLOCKED. Local review is still not authenticated
issuer authority or verified consent. This stricter integration was added during
pre-execution development; no human classifier outcomes existed or were changed.
