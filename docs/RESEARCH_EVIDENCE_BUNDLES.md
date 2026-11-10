# Research evidence bundles — schema 1.0.0

`EvidenceBundle` is an immutable canonical-JSON reference manifest using existing
Soma canonical serialization, SHA-256, protocol fingerprints and native result I/O.
It is not a second workflow engine or a legal/consent verification service.

The manifest binds dataset/version, protocol fingerprint, local creation time and
1–128 uniquely named evidence entries. Entries contain an opaque identity, kind,
SHA-256, issuer/source identities, document version if known, issue/validity/expiry/
revocation timestamps, intended purpose/actions, distribution limit and human-review
status/reviewer/time. Supported kinds include registration, agreement, license,
consent, IRB, identity, preprocessing, BIDS validation, transform, QC, protocol seal
and dataset snapshot. Unknown schemas, duplicate entries and invalid intervals fail.

Restricted documents remain private. Their locations are supplied separately as an
explicit allowlist of root/relative-path pairs. Parent traversal, absolute references,
escaped symlinks, oversized files and unbound references fail before use. No document
is copied or uploaded. Repository examples contain fictional metadata only.

`seal_bundle` creates a deterministic content address; `write_bundle` writes a
canonical manifest/seal exclusively with private file permissions. An existing file
cannot be overwritten. `read_bundle` verifies its seal. `verify_bundle` rechecks live
bytes and reports integrity separately from validity/review reasons. Modification
requires a new content-addressed bundle; it does not modify historical evidence.

A matching SHA-256 proves correspondence to a trusted reference, not the truth,
authenticity or authority of a document. Issuers/reviewers are explicit local
assertions, not independently authenticated signatures. Software cannot infer IRB
approval or participant consent. Historical receipts do not discover provider/portal
revocations; current evidence and review are required before reuse.

Permission readiness extends M20's purpose/action/source checks. The exact source
must be bound in the bundle; agreement versions must agree where specified. Unknown,
required/rejected/conflicting review, changed/missing content, expiry, revocation,
future timestamps, unsupported scope and incompatible distribution restrictions block.
Raw participant-record export remains denied even if an assertion claims otherwise.
Every output retains `legal_authorization_established=false` and `consent_verified=false`.

See the wholly fictional [SDK example](../examples/research_readiness.py). Real
bundle manifests, signed documents and participant identities belong in ignored
local storage, never Git. Preprocessing manifests with relative participant asset
mappings are private import configurations, not public provenance exports.
