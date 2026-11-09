# MRI pipeline architecture — decision record M12

Status: accepted before implementation, baseline0148813, Soma0.11.0/636 tests.
The execution model is a local, serial, typed DAG, not a distributed scheduler.
Existing Volume, VoxelMap, Frame/Transform, NiBabel loader/writer, RAS/LPS SimpleITK
bridge, resample, tissue metrics, surfaces/topology, provenance manifest,
AnatomyReport and physical cache are the numerical/provenance authorities.

## Contracts

An InputRecord binds immutable source path/hash, dataset type, subject/session,
source entities, contrast, inherited metadata and explicit legacy conversion.
PyBIDS indexes genuine BIDS inputs; legacy records reuse human_mri loaders and
never pretend the original source was BIDS. MRBrainS permits training partition
only. Selection is one explicit subject/session/acquisition per run; ambiguity
fails unless a documented first-sorted policy is chosen. Never average scans.

StageSpec declares dependencies, input/output types, RAS metre coordinates,
parameters, dependency versions, implementation identity and failure rules.
The graph is validated for missing dependencies, output collisions and cycles.
Ingestion -> geometry -> intensity -> preprocessing -> mask -> segmentation ->
label validation -> optional surfaces -> mesh QC -> report -> derivative export.
Data dependencies prevent invalid artifacts reaching later stages. Invariant
failures stop the subject, structured run journals preserve the failed stage.
Anatomical plausibility is separate from numerical validity.

## Execution and cache

Use existing cached_object/fingerprint and atomic_json. Stage keys bind input
artifact/file content, parameters, source tree, dependency versions, subject,
geometry, transforms and ontology. Whole-source invalidation is conservative.
Unchanged volumes are referenced as aliases rather than duplicated in each cache.
Fresh and reused stages both read their serialized artifacts. Logs distinguish
hit/miss, recovery, failure and bypass. Missing half-published caches can be
quarantined on explicit recovery; committed corruption fails closed unless
explicit cache repair is requested. Source data and completed derivatives are
never overwritten. Resume requires identical run identity and output hashes.
New configuration requires a new run/output, but unchanged stage keys may reuse
compatible cache entries. No implicit cache transfer across source identities.

## Processing and backend boundary

Default preserves the fixed multi-Otsu baseline: no N4, mask application,
normalization, spatial resampling or registration. N4 is opt-in SimpleITK with
bounded threads/iterations, geometry roundtrip and convergence diagnostics.
Explicit masks must match image/subject geometry; generated threshold masks
remain heuristic foreground candidates, not validated brain masks. Optional
resampling uses an explicit reference grid and identity-world transform; this is
not registration. Existing RAS metre Transform objects record source/destination,
direction, composition/inversion, interpolation, input/output grids and provenance.
No nonlinear transform can be serialized as a matrix.

Backends implement a protocol: input Volume + identity/options -> segmentation
Volume + tool/version/model/contrast/ontology/mapping/runtime/warnings receipt.
Built-in multi-Otsu and validated precomputed-import adapters are required. External
implementations are registered explicitly; no weights or large tools are fetched.
All outputs must have compatible native geometry and documented tissue semantics.

## Export and QC

BIDS derivatives contain only supported preproc T1w, binary mask, discrete dseg,
sidecars and custom-label TSV. Soma's CSF1/GM2/WM3 differs from BIDS defaults, so
explicit TSV mappings are mandatory. GeneratedBy and source relationships identify
Soma and original BIDS versus legacy origin. Custom stage logs, transforms, mesh
arrays, figures and metrics stay in a separate Soma report root, not disguised as
standardized derivative suffixes. Output privacy guards permit only ignored
reports/data-derived/derivatives locations inside this checkout. Dataset description
and subject export are atomic/exclusive; resume validates existing products.

PyBIDS indexing and Python filename validation are not full BIDS certification.
An available official schema validator is run locally; absent/failed external
validation is INDETERMINATE/FAIL, never an invented compliance PASS. QC distinguishes
numerical PASS/FAIL, heuristic flags, external tissue evidence and unsupported
anatomical/clinical claims. BEM readiness stays INDETERMINATE.

## Prespecified acceptance experiments

Preserve prior M11 results/seals. Run all18 IBSR development and all5 permitted
MRBrainS training cases with the baseline-preserving default; compare per-subject
metrics to the earlier fixed baseline without refitting. These MRBrainS subjects
have been inspected and are not fresh holdouts. Optional N4/resampling/mask/surface
experiments use separate synthetic configurations and selected development-only
MRI demonstrations, never label-tuned external accuracy claims. Test synthetic
BIDS metadata inheritance, ambiguous selection, standards validation, geometry,
backend import, interrupted-stage recovery, corruption detection, resume cache
reuse and immutable derivatives. Save underlying plot arrays and performance.
Only aggregate verification/code is committed; no individual medical information,
MRI images, raw data or private source fingerprints. No push, no M13.
