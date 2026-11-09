# Milestone 1 workflows

Run `soma experiments synthetic-spectrum --output reports/synthetic-spectrum`.
For real EEG, explicitly fetch S001R04 then run `soma eeg analyze` as shown in
the root README. Orchestration is in `soma.signal.experiments` and
`soma.eeg.analysis`; this directory intentionally contains no duplicate algorithms.

Milestone 8 uses `milestone8/run.sh` after explicit sample fetching. Its compact
`milestone8/verification.json` records the executed participant/synthetic results;
large data, FIF caches and figures remain ignored under data/ and reports/.
See docs/INDIVIDUAL_SOURCE_VALIDATION.md for the conditional anatomical status.

Milestone 9 uses `milestone9/run.sh` with cached MNE sample assets and preserved
M8 report arrays. Its initial audit and final verification receipt are committed;
large reports remain local. Read docs/MILESTONE9_RESULTS.md before interpreting
proxy fiducial residuals, current attenuation or normalized source statistics.

Milestone 10 uses `milestone10/run.sh` after explicit selected reference fetches.
The supplemental `interaction_analysis.py` processes all prespecified groups,
retaining input/code hashes and paired intervals. Initial inspection and final
verification receipts are committed; raw references and generated reports are not.
See docs/MILESTONE10_RESULTS.md for scientific scope and unresolved limitations.


M11: `milestone11/fetch_sci.py` verifies pinned explicit SCI acquisition;
`milestone11/run.sh` executes six real CLI actions and a public MNE comparison.
The protocol is sealed before evaluation; external-discovery, initial-inspection
and verification receipts preserve access limits, old results and source identity.
Tissue/holdout CLI reports explicitly unavailable registered data, not success.
See docs/MILESTONE11_RESULTS.md for numerical results and the authorized version-test correction.


M11 human integration: `milestone11-human/run.py` reproduces the explicit local
inventory/development/freeze/external sequence with the new human-tissues seal.
Its MRI inputs and all participant outputs stay ignored. The committed verification
receipt is aggregate only; full per-subject tables, pictures and hashes are private
local artifacts. Historical M11 experiments remain unchanged.
