# Milestone 1 workflows

Run `soma experiments synthetic-spectrum --output reports/synthetic-spectrum`.
For real EEG, explicitly fetch S001R04 then run `soma eeg analyze` as shown in
the root README. Orchestration is in `soma.signal.experiments` and
`soma.eeg.analysis`; this directory intentionally contains no duplicate algorithms.
