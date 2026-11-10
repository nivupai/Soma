# Human data readiness gates

Readiness is a read-only extension of M19 seals and M20 human planning. It does not
create another DAG, estimator, execution engine or authorization service. Reports use
M17 `experiment.manifest` native result envelopes and their existing integrity checks.

`execution_readiness` recomputes live source/bundle checks, exact dataset/version,
frozen cohort/protocol scope, existing scientific conformance, permission review,
preprocessing/QC and optional registration/session requirements. Readiness policy is
sealed in the existing protocol's optional metadata; it only adds restrictions and
cannot bypass M20 science/inference restrictions. There is no operator gate override.

| Gate status | Meaning |
| --- | --- |
| READY | Required checks for this particular gate have sufficient supported evidence |
| BLOCKED | A required check fails or required evidence is unavailable |
| INDETERMINATE | Evidence cannot establish the required scientific property |
| NOT_APPLICABLE | The frozen plan does not require this gate |

Any BLOCKED gate blocks the aggregate. Otherwise INDETERMINATE is retained. An
aggregate cannot omit or override an individual recording's blocked gate. All
selected recordings remain present; unfavorable QC never creates silent exclusions.
Readiness-only protocols cannot be dispatched through the legacy human runner.
The retrospective EEG pilot has a separate existing descriptive protocol; its completion
does not dispatch or satisfy the longitudinal readiness protocol.
READINESS READY is not workflow execution permission. Human confirmation is always
blocked when requested. Consent/legal authorization and reliability remain unverified.

Historical native reports can be inspected but must not be replayed as current
permission. Explorer labels them as receipts not revalidated, exposes a compact
session/task table and gate/reason summary, and never runs science or retrieves a
provider on GET. Restricted documents, private paths, raw images and individual
scientific outcome rows are not exposed by this view. Underlying preprocessing import
manifests and private agreement locations are not served.

CLI:
```
soma registration verify-attachment --help
soma evidence inspect BUNDLE
soma evidence verify BUNDLE REFERENCES_CONFIG
soma preprocessing audit MANIFEST REQUEST_CONFIG RAW_ROOT DERIVATIVE_ROOT
soma sessions validate IDENTITY_MANIFEST --chronology-required
soma research readiness CONFIG --output PRIVATE_OUTPUT
```
Registration retrieval needs `--network`. Other audit commands never access providers.
Reference configurations use explicitly selected roots and relative files. A readiness
configuration supplies the existing M20 request, evidence bundle/reference files,
explicit preprocessing manifest list and raw/derivative roots. No shell commands,
automatic filesystem-wide discovery or upload facility are accepted.
