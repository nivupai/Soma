# Scientific drift classification

Comparisons report observations and their evidence separately. Multiple categories
can coexist. None of these categories establishes biological change.

| Category | Evidence |
| --- | --- |
| DATA_DRIFT | Snapshot hash, aligned unit/session additions/removals and observed input fingerprints |
| PROTOCOL_DRIFT | Structural scientific declaration/requirement changes |
| IMPLEMENTATION_DRIFT | Actual installed Soma source fingerprint |
| EXECUTION_ENVIRONMENT_DRIFT | Actual OS/Python/library/build identities |
| NUMERICAL_DRIFT | Changed aligned summaries with unchanged methods/inputs and frozen bounds |
| MEASUREMENT_OR_OUTCOME_DRIFT | Changed selected output summaries; biology NOT_ESTABLISHED |
| MISSING_OR_UNVERIFIABLE_EVIDENCE | Missing/incomplete units or no aligned completed observations |

Numerical equivalence uses `abs(a-b) <= atol + rtol*abs(b)` with exact shape, axis
and unit requirements, finite values and explicit missingness. Tolerances are copied
from the frozen M18 policy backed by M17 independent numerical oracles. They are
never widened after outcomes. Changing the tolerance policy is a scientific amendment.
Agreement is limited to selected summaries, not full arrays or universal study
equivalence. Different inputs or methods produce descriptive differences with
numerical equivalence marked inapplicable. A failed bound remains a failed bound.

Exact output-file bytes, numerical identity, tolerance agreement, protocol identity,
input content and cache identity are separate evidence. A statistical significance
test is not a numerical-equivalence test. No summary comparison authorizes cache
interchange, human reliability, anatomical accuracy or confirmatory replication.
