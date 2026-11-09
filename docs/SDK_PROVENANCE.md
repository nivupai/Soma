# Provenance and result contracts

The SDK extends `soma.core.provenance.manifest`: application version, source,
parameters, paths, seed, UTC timestamp, Git context when available, Python and
library versions remain present. Installed artifacts normally have no Git context;
missing revision is recorded as None rather than inferred from the user's project.

`result_metadata` additionally requires an input SHA256, method identifier, explicit
parameters, units, data identity, estimand, spatial reference (explicit None for
nonspatial work), interpretation state, warnings and source provenance. It permits
synthetic/descriptive/unavailable states and always records confirmation=False.
The original GLM policy remains the authority for statistical inference. Method-
specific result types remain unchanged and should accompany this metadata.

`array_fingerprint` hashes dtype, shape and C-order bytes with no rounding; `sha256`
streams files. A hash does not anonymize a participant or grant data-sharing rights.
`require_comparable` conservatively rejects differing/missing schema, software
version, method, units, data identity, estimand, spatial reference, interpretation
or parameters. Put explicit ontology and contrast definitions in parameters.
Different input fingerprints can describe independent predictions of the same
identified target. Compatibility never authorizes pooling or establishes accuracy.

Strict JSON rejects NaN/Infinity and nonserializable objects. `write_json` refuses
existing files. `read_manifest` accepts a JSON object without inventing missing
fields. Manifest inspection is not an export sanitizer: local provenance may
contain participant IDs or source paths. Keep such records in ignored local outputs.
Explorer exports continue through its existing sanitizer and allowlisted registry.

Historical verification records contain `<LOCAL_HOME>` placeholders and original
execution IDs as documented in PRIVATE_PUBLICATION.md. They were not regenerated
for this milestone. No old unsanitized repository/history is an SDK dependency.

Execute `python -m examples.provenance` for strict roundtrip/comparison checks.
