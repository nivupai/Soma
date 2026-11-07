# ADR 0005 — sealed protocols and subject calibration

Accepted for Milestone 4. Preserve the established EEG numerical backend, adding
thin per-record checkpoints and streamed table aggregation. Freeze both protocol
configuration and narrative before accessing the new cohort. Primary estimands
and eligibility remain fixed; sensitivity variants cannot replace the primary.

Use SciPy bootstrap/BCa and analytic mean standard errors. Explicit failure
statuses are preferable to method substitution. Separate observed-data target
coverage from structural-truth coverage in biased/missingness models.

Bound process workers and queued chunks; derive random streams from stable
experiment coordinates, not worker IDs. Publish checksummed chunks and immutable
summary generations. Inference accepts independent subject effects; trials do
not cross the population resampling boundary. Median/trimmed and trial/run
weighting retain distinct interpretations.
