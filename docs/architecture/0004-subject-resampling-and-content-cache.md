# ADR 0004: subject-level replication and content-addressed run artifacts

Status: accepted for Milestone 3.

The scientific unit is a subject, not a pooled trial. Pair within run, average
runs within subject, then resample subjects. Missing pairs remain unavailable.
Prespecified one-factor-at-a-time variants expose robustness without selecting a
favored configuration. Pointwise percentile intervals are nominal and have
poor small-n coverage in the recorded laboratory; no significance claim follows.

Reuse the existing motor-imagery engine for each recording. Cache immutable
numeric/table artifacts by source fingerprint, numerical settings and relevant
software/source identity. Failures are records, not silent cohort exclusions.
Sequential processing limits memory growth and preserves recording boundaries.
Cache all exact run results before inventing a layered optimization framework.
Burst thresholds stay calibrated in volts despite NeuroDSP's internal median
normalization; mapping uses actual valid exposure and explicit censoring.
