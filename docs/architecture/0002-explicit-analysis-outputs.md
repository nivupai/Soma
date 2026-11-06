# ADR 0002: explicit selection and immutable execution directories

Status: accepted for Milestone 1.

Downloads occur only on explicit subject/run requests. Experiment outputs each
get a new directory, strict JSON manifest and human-readable report. The cost is
that reruns need new names and failed runs may need manual cleanup. This is
preferable to silent overwriting or background bulk downloads. Whole-record
spectral summaries remain descriptive until event segmentation and inference
are validated in a subsequent milestone.
