# Fitted model serialization

M24 composes existing M17 numeric storage and M23 capsules. No pickle, executable
object reconstruction, estimator deserialization or missing-component fitting is
supported. A release lives in ignored private storage with relative references:

- `manifest/result.json`: versioned `soma.model-release/1` manifest.
- `models/<family>/result.json` and `arrays/*.npy`: five M23 capsules.
- `probe/result.json`: original prediction-session features, labels/scores and supported probabilities.
- `source-validation/`, `source-cv-audit/`, `input-evidence/`, `reload/`: private evidence.

The release ID is the canonical digest of the manifest values excluding its own ID.
It binds the M19 seal, source-data/inventory fingerprints, model identities/file
hashes, contract/class order, software/source identity, environment, backend,
pyriemann version, tolerances and verification declarations. M17 additionally binds
metadata and every array file/content hash, dtype and shape. Metadata-only integrity
is not authentication of an author or evidence of scientific independence.

| Family | Prediction-complete fitted components |
|---|---|
| Majority | Source class1 prior; fixed tie decision policy |
| Log band-power LR | Ordered scaler mean/scale, binary coefficients/intercept |
| CSP LDA | Four ordered sensor projection filters, binary LDA coefficients/intercept |
| Riemannian MDM | Two ordered SPD class-reference covariances; fixed Riemannian distance rule |
| Tangent LR | SPD source tangent reference, isometric mapping convention, scaler mean/scale, coefficients/intercept |

Class order is0/1 throughout. CSP computes log mean squared projection of volts
converted to microvolts. Power features are natural logs of integrated V² PSD;
covariances use µV². Logistic/LDA class1 probabilities use the binary sigmoid;
MDM exposes distance decisions without claiming calibrated probabilities. Inference
requires precisely ordered float64 `(n,9,320)` epochs, `(n,9,2)` log powers and
`(n,9,9)` covariances under the declared contract. Trial-local features are computed
before the prediction call; the reload operation calls no estimator fit method.

Prediction needs the stored scaler scale, not a newly estimated variance. CSP
patterns and LDA generative covariance internals are not needed by the exported
prediction kernel; this is complete supported prediction state, not restoration
of every introspection field of the original sklearn/MNE object.

The importer rejects unsupported versions, absent source fingerprints, wrong
protocol/model bindings, missing components, changed coefficients/hashes, nonfinite
values, wrong array precision/shapes, inverted class/order, invalid scales and
non-SPD references. Bounded M17 reads reject unsafe references, object arrays,
symlinked numeric files and oversized allocations. The M23 default environment and
source-code guards remain unchanged. No fallback learns or imputes missing state.

Real model arrays remain private. The public aggregate whitelist excludes arrays,
coefficients, participant rows and paths. The Explorer accepts only the dedicated
metadata summary method, never a private release or capsule manifest.
