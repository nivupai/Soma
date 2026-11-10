# Controlled workflow replay

The typed public API is `soma.sdk.protocol`. Protocol requirements project the
existing M18 graph into immutable registered stage contracts, parameters, units,
spatial/temporal metadata, seeds and QC requirements. Runtime operation names come
from a fixed registry; documents cannot import Python, shell commands or plugins.
The fMRI adapter calls existing Soma GLM/design/contrast code. Numerical algorithms,
result schemas and exact-environment M18 caching semantics are unchanged.

`plan` validates without scientific execution. `run` requires an explicit sequence,
sealed protocol and bounded dataset snapshot. CONTROLLED and EXPLORATORY require a
complete reference execution. The seed schedule hashes study ID, unit, session and
master seed; collisions are rejected. New stochastic realizations have independent
streams. Every scheduled unit remains in records, including missing/blocked/failed
units. Eligibility adapters support only the explicit synthetic generator scope;
unimplemented human eligibility/session/permissions cannot claim compliance.

| Mode | Requirements and interpretation |
| --- | --- |
| EXACT | Identical full protocol, snapshot/input identities, implementation and actual complete M18 environment evidence. Report file-byte, numeric identity and frozen numerical equivalence separately. |
| CONTROLLED | Unchanged science; only prespecified snapshot, added-unit, session, supported environment or explicitly amended editorial differences. No selective removal. Different inputs permit descriptive comparison, not numerical-equivalence claims. |
| EXPLORATORY | Explicit increasing parent amendment. Scientific method changes remain descriptive. Unsupported methods are blocked rather than replaced. |

Post-execution comparisons check observed input/output evidence, not declarations
alone. Source implementation changes have no compatibility waiver. Actual software
versions/build fingerprints must satisfy the frozen platform/range policy. A
compatible platform does not grant cross-environment cache reuse. Missing evidence
is INDETERMINATE; incompatible methods in CONTROLLED are REJECTED.

`example_protocol`, `example_snapshot`, `seal`, `plan`, `run`, `compare`,
`conformance`, `history`, `append_history` and `redact_export` are supported SDK
operations. See `examples/research_protocol.py`. CLI commands are `protocol
validate/seal/compare/audit`, `replay plan/run/compare/drift`. `replay run --dry-run`
does not execute scientific stages. A rejected run/compare exits nonzero.

Four demonstrations run using `scripts/run_protocol_demonstrations.py`. They are
new synthetic studies, not retroactive upgrades of historical experiments.
