# Workflow cache identity, version 1

Design contract established before implementation. New workflow caching is opt-in;
existing MRI/cohort caches and numerical algorithms retain their prior contracts.
The DAG reuses pipeline StageSpec ordering and encode/decode, and the existing
staged-directory publication pattern. It is a bounded serial extension, not a
distributed scheduler or automatic migration of old workflows.

SHA-256 over explicit typed canonical values distinguishes int/float/bool, ordered
lists and mapping keys. No repr, mtime or memory addresses. Logical stage identity
binds implementation/source digest, algorithm and software versions, all algorithm
parameters, input derivation/content identities and scientific contracts, seeds
and stream, precision and numerically relevant execution settings. Presentation
preferences are stored separately and excluded. All relevant input declarations
must be known; INDETERMINATE metadata cannot justify reuse.

Execution environment identity is separate: OS/architecture/Python, byte order,
resolved scientific dependencies, reported math backends and numerical thread
settings. Cache identity binds both logical and environment identities. Environment
changes conservatively miss even when a numerical replay passes tolerances.
Artifact identity binds producer cache identity, output role/type, scientific
metadata and content. File SHA-256 is distinct from these semantic identities.
A checksum demonstrates integrity, not scientific correctness or authorship.

Published entries are immutable. Reuse requires schema validation, full linked
array/metadata hashes, expected producer/version/stage/environment identities,
input lineage and explicit scientific compatibility. Corruption fails closed;
resume never silently repairs published artifacts. Temporary unpublished staging
directories are not candidates for reuse. See recovery and provenance specs.

Stable graph-node/port bindings also enter the execution cache identity. Identical
computations in distinct named branches cannot collide with incompatible output
receipts. Logical identity remains separate from that binding and environment.
Dependency derivations propagate producer keys; observed input-content fingerprints
are independently checked against each stage receipt and envelope on reuse.
Canonical content fingerprints replace local array aliases with actual dtype,
shape and byte fingerprints, so mapping order cannot change scientific identity.

External in-memory inputs are validated and snapshotted before any stage runs.
String mapping keys are required; metadata cannot silently collapse integer/string
keys. The shared codec normalizes tuples to JSON lists on both cold and cached
consumption. Numerical dtype/shape/bytes retain their explicit identity. Result
identity combines output derivation and content; per-file SHA-256 remains separate.

The source digest conservatively covers Soma's Python scientific implementation.
A code change can invalidate more than a parameter change; this favors correctness
over hit rate. Exact dependency versions are included. Changing a graph's separate
presentation preferences does not change numerical keys. No universal semantic
proof of third-party algorithms or malicious runtime modifications is claimed.
