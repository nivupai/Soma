# Bounded historical migration

The reviewed machine-readable inventory is experiments/milestone17/artifact-inventory.json
(16 existing families). migration-fixtures.json selects four sources explicitly;
there is no bulk converter for885+ old artifacts. Original report/test bytes are
checked against the sanitized v0.16 baseline and remain unchanged.

Adapters:

- core-manifest-v1: requires original integer schema_version=1; retains full JSON.
- sdk-metadata-v1: requires sdk_schema_version=1; retains full JSON.
- milestone-verification-json: explicit generic JSON verification/excerpt record.
- welch-manifest-v1: explicitly selected synthetic channel, recorded Welch metadata
  and library identity, adjacent bounded spectra.npz with exact expected keys.
  Frequencies/density are retained exactly; reference/time-origin/source-code
  uncertainty remains recorded. No stored absolute output path is followed.

Generic adapters yield legacy.record/INDETERMINATE. The Welch adapter can preserve
an actual numerical PSD contract, but remains INDETERMINATE because original
array authentication, reference and alignment information may be absent. Insufficient
metadata never becomes a guessed coordinate conversion or validated inference.
When the numerical adapter lacks required metadata, use the generic read-only
manifest adapter or recover original evidence; do not synthesize missing fields.

Receipts identify source format/hash, original canonical JSON hash, migration Soma
version, selected channel, missing knowledge and numerical-preservation status.
Hashes observed during migration are not retroactive authentication of the original
execution. Source paths are portable review references; upgraded files stay in
ignored reports, retaining original provenance even when it contains local paths.
Those strings are archival context, never prerequisites for locating payload files.

CLI defaults to a dry run: soma results migrate FILE --source-format FORMAT.
Only an explicit --output NEW_DIRECTORY writes a separate upgraded artifact.
Existing directories/files are never overwritten. Source bytes are checked again
after reading. No original timestamps, identities, units or validation status are
invented. See migration-receipt.json for actual reviewed coverage and missing fields.
