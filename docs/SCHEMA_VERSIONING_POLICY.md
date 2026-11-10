# Schema evolution and compatibility policy

Software version and file-format schema version are independent. Supported result
schemas are soma.result1.0.0 and1.1.0; newly created results use1.1.0. Historical
core manifests with integer schema_version=1 and SDK sdk_schema_version=1 are
separate formats, never implicitly treated as result envelopes.

1.1.0 adds optional warnings/migration metadata to the1.0.0 contract. Use
upgrade_schema explicitly; it copies payload, checksums of numerical files and
original provenance without numerical conversion, recording source schema and
migration software. Producer release differences alone do not change estimands.
Unknown minor/major versions fail with an actionable unsupported-version error.
Unknown fields fail; future optional additions require an explicitly supported
version before reading, preventing accidental interpretation of new semantics.

Unit/coordinate/estimand changes are not metadata cosmetics. They require a named
conversion with preserved source provenance, a different schema contract, or
recomputation. No adapter may turn BOLD into EEG power, native into template space,
or one correction/noise model into another. Method versions must change when
numerical meaning changes. Omitted knowledge cannot be inferred by an upgrade.

Read-only migration never edits source bytes. A valid file can be scientifically
INDETERMINATE; integrity and compatibility are independent from statistical,
anatomical and clinical validity. No schema upgrades the human fMRI inference policy.
