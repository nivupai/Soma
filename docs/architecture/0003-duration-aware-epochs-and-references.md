# ADR 0003: duration-aware epochs and separate spectral power conventions

Status: accepted for Milestone 2.

MNE event onsets alone do not define task durations or valid pre-cue references.
Soma retains typed annotation durations and original coordinates, validates event
tables, and logs every proposed extraction. Continuous preprocessing runs before
analysis windows and carries a measured operational recording-edge guard.

Welch PSD and MNE Morlet power have different normalization; each is compared only
with its own estimator's valid-rest output. Absolute results survive unavailable
references. References never cross runs. Explicit NaN masks replace epsilon
repairs. Fixed dimensional arrays with named coordinates meet the present need
without introducing xarray or a speculative imaging framework. Template geometry
provenance remains replaceable by future measured DigMontage data.
