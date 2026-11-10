# Research-use evidence and software permission checks

`soma.human.permission/1.0.0` records dataset/version, local access source,
agreement identity/version (unknown is explicit), source URI or opaque local reference,
source SHA256, authority, license assertion, purposes, actions, restrictions, review
status/time and optional expiry. Individual consent is NOT_VERIFIED. A file on disk
establishes access, not authorization, consent or scientific validity.

Known public notice profiles support bounded local methods research and aggregate
exports only. EEGBCI's official [version 1.0.0 page](https://physionet.org/content/eegmmidb/1.0.0/)
identifies ODC-By 1.0 and conditions access on that license. IBSR's inspected local
Rohlfing release notice states public domain and requests citation; that notice is
retained as content-bound evidence for this selected release, not generalized to
other IBSR releases or assets. ds000114's local dataset description declares CC0.
MRBrainS's supplied Readme/manifest establish format and partition, but contain no
sufficient agreement for this pilot, so its analysis is blocked.

The checker requires dataset/version, source bytes, purpose/action and review status
to agree. Unknown, revoked, conflicting, expired, changed or unsupported evidence
refuses execution/export. Native caches bind permission fingerprints; changing the
review context cannot reuse an old result. Raw/participant-record export and
redistribution remain unsupported even if a local declaration lists them as actions.
Permission is checked before dispatch and inside the registered operation. No consent
or legal authorization is inferred. Offline checks cannot discover unreported portal
revocations or authenticate an operator's assertions.

Use ignored `*.local.json/yaml/yml` configurations. Keep keys and agreement files
outside Git, and use opaque source identifiers plus hashes rather than embedding
private paths or agreement bodies. Source paths belong only in explicit local request
configuration. Pilot output roots and key files are private; public summaries contain
operational counts, not participant mappings, metric rows, images or agreements.
