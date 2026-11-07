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
