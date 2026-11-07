# Additional reliability findings and implementation corrections

These findings arose during the prespecified development audits after the original
M9 protocol freeze. They are additional diagnostics, not rewritten primary
choices, surface repairs, altered source filtering or optimized regularization.
Original M8 reports and both frozen protocols remain intact.

The prespecified shallow-source selection found source 621 only 0.675925 mm from
an inner-skull triangle, despite MNE's mindist=5-mm parameter. Its nearest inner
skull **vertex** is 6.591712 mm away; 104 retained sources have triangle distance
below 5 mm. Installed MNE 1.13.2 `_filter_source_spaces` calls `_CheckInside.query`,
which uses a KDTree over surface vertices. Thus that setting is not an exact
continuous triangle-clearance guarantee. This is a limitation/clarification of
what the historical MNE parameter establishes, not evidence of a Soma transform
or conductivity error. The extra report retains all original source identities,
adds exact distances and flags submillimetre clearance without certifying safety
or declaring numerical instability from a retrospectively chosen cutoff.
The existing independent point-to-triangle numerical test distinguishes vertex
and surface distances; the new opt-in reliability test validates the actual
retained-source observation. Future source-space changes require a separately
prespecified comparison with physical correspondence, not a silent correction.

Primary implementation references (also inspected in the installed package):
[MNE source-space filtering](https://github.com/mne-tools/mne-python/blob/main/mne/source_space/_source_space.py),
[MNE surface-distance query](https://github.com/mne-tools/mne-python/blob/main/mne/surface.py).

A new M9 evidence-report implementation initially used `dataclasses.asdict` on
provenance containing MNE's list subclass for bad channels. Recursive dataclass
conversion called that subclass's unsupported constructor. The report failed
explicitly; no successful old report or numerical array was changed. Evidence
serialization now explicitly maps its own fields and preserves JSON-compatible
provenance containers. An offline regression test covers this correction.

Final manifest validation also detected stale installed metadata (0.8.0) despite
0.9.0 source. The first no-isolation editable installation had failed because its
build backend was unavailable. A successful isolated editable installation now
records 0.9.0, and all five workflows were rerun into a new validated directory.
Earlier report attempts were not relabeled or overwritten. A regression assertion
checks installed versus source version. This corrected environment/provenance,
not the scientific computation or historical M8 results.
