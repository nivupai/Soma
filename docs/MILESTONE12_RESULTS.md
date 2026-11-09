# Milestone 12 — anatomical processing engine results

Soma v0.12.0 extends baseline `0148813` with a serial, inspectable MRI DAG,
PyBIDS ingestion, legacy bridges, conservative preprocessing, backend adapters,
private BIDS derivatives, content caches, recovery and explicit QC evidence.
The accepted architecture and configurations were sealed before processing in
`configs/milestone12-freeze.json`. Historical reports are unchanged.

## Acceptance and tests

The baseline had 636 passing tests. All 45 original test files remain byte-identical.
Fifty-five new cases pass, covering geometry, independent RAS/LPS oracles, physical
volume, nearest-neighbor labels, BIDS inheritance/ambiguity, schema validation,
backend identity, masks, corrupted inputs/caches, wrong subjects, atomic export
and interruption/recovery. Full pytest including cached integrations: **690 passed,
1 failed**, 62 warnings, 73.52 s. Default offline selection: **673 passed, 1 failed,
17 deselected**, 60 warnings, 48.17 s.

The sole failure is the unchanged historical
`test_protocol_and_installed_version_match_source`, which requires version
0.11.0. Source and installed package correctly report 0.12.0. The user explicitly
instructed: “Keep it unchanged and record its failure.” It is neither skipped nor
xfail-marked. Consequently the all-tests-pass acceptance criterion is unmet by
that directed exception; no numerical regression is hidden. Ruff lint and format,
strict mypy (159 source modules) and dependency checks pass.

## Ingestion, geometry and standards

PyBIDS 0.22.0 indexes synthetic raw subject/session/acquisition records, inherits
JSON metadata and rejects ambiguous selection. The tested raw synthetic dataset
passes the official validator. No new human raw BIDS cohort was acquired.
IBSR and MRBrainS remain legacy non-BIDS inputs, with source identities and existing
conversion assumptions preserved privately. Multiple scans are never averaged.

All 18 IBSR cases and five MRBrainS labeled TRAINING cases completed. Existing
IBSR singleton-frame/mm/sform interpretation and MRBrainS qform/sform conflict
handling are recorded. Existing limited identity-world MR intensity alignment is
preserved; no fitted registration or label resampling was introduced. The default
adds no N4, mask application, normalization, grid resampling or surfaces.

Both human derivative datasets pass structural indexing and the **official
bids-validator-deno 3.0.2**, using local **BIDS 1.11.2** schema and no network
permission: 36 IBSR and 10 MRBrainS image files. The synthetic default, optional
all-stage and development-only N4 derivative datasets also pass. Warnings remain
in private validator JSON: missing derivative README, too few authors and
recommended sidecar fields. PASS describes the supported exported schema only.
Custom plots, transforms and journals remain outside standardized derivatives.
Explicit TSVs map Soma CSF1/GM2/WM3 to BIDS tissue meanings; label codes are not
silently interpreted using BIDS defaults.

## Reference-based results

Predictions use independent, unchanged Soma multi-Otsu T1 intensity segmentation,
with no reference input to the backend. No external segmentation tool or learned
weights were fetched. Precomputed imports and explicit external adapter registration are
software interfaces tested synthetically, not new human methods evaluated here.
The largest per-subject difference from the frozen M11 Dice, Jaccard, ASSD, HD95
and signed-volume metrics is **0.0** in both datasets (69 tissue rows).

| Dataset | Subjects | Mean macro Dice | Subject bootstrap 95% CI |
| --- | ---: | ---: | --- |
| IBSR development | 18 | 0.587345 | 0.576293–0.598602 |
| MRBrainS known training evaluation | 5 | 0.455683 | 0.361946–0.546850 |

Bootstrap seed 12042 differs from the historical seed; CI changes do not represent
changed predictions. These small subject intervals omit inter-rater uncertainty.
MRBrainS results were previously inspected and are **not a fresh external holdout**.
No hidden test labels were read or evaluated.

| Dataset | Tissue | Dice | Jaccard | ASSD mm | HD95 mm | Signed volume difference mL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| IBSR | CSF | 0.111281 | 0.059576 | 26.7849 | 43.3724 | +273.709 |
| IBSR | GM | 0.784953 | 0.647584 | 1.0971 | 3.2961 | -234.535 |
| IBSR | WM | 0.865802 | 0.764372 | 0.8223 | 3.1949 | +55.360 |
| MRBrainS | CSF | 0.478159 | 0.314534 | 5.6107 | 21.2025 | +531.877 |
| MRBrainS | GM | 0.526356 | 0.358348 | 7.7195 | 32.5465 | +599.531 |
| MRBrainS | WM | 0.362533 | 0.259236 | 11.7055 | 38.9406 | +168.663 |

Entries are means across subjects, not pooled voxels. Volume is prediction minus
reference, determinant-based mm³/1000. Private tables also preserve absolute and
relative volume errors. Physical boundary metrics retain the existing area-weighted
voxel-face definition. MRBrainS cerebellum/brainstem labels 7/8 are excluded from
scoring without becoming background truth or prediction features. Source ontology
mapping/coverage limitations remain as documented in M11.

## Stage coverage, recovery and optional experiments

All eleven DAG nodes execute for each subject; disabled processing is explicitly
bypassed, not represented as an actual N4/surface computation. Geometry, finite
intensities, label semantics and export invariants pass for 23/23 human cases.
Anatomical plausibility and BEM readiness remain INDETERMINATE.

A separate synthetic experiment exercises N4 (two bounded iterations), a threshold
ROI mask, linear reference-grid resampling from 25³ to 23³, tissue segmentation,
WM surface extraction and topology. Its surface has 270 vertices, 536 faces,
Euler characteristic 2, zero boundary/nonmanifold edges and no detected nonadjacent
intersections under the stated checks; this is a synthetic numerical result.
A separate first-development-case N4 demonstration uses two iterations/shrink 4
on already processed IBSR MRI. It is not a tuned human accuracy comparison.

A new synthetic output reuses **11/11 stage caches**. Deliberate interruption after
preprocessing resumes from **4** committed stage hits. Corrupted committed cache
fails closed; explicit repair quarantines and rebuilds it. Unit tests additionally
cover half-published cache and crash-after-export recovery without overwrite.
All 23 completed human resumes verify final hashes; they perform **zero stage-cache
reads**, correctly distinguished from stage cache hits. Initial cohort runs already
had 22 compatible cache hits, so their timing is not a completely cold-cache claim.

## Runtime, memory and inspected artifacts

One worker, OPENBLAS/ITK threads 1, local macOS environment. The human benchmark
used 155.225 s wall, 150.603 s CPU and 820.156 MiB whole-process peak RSS (including
libraries). IBSR initial processing/scoring/figures took 109.147 s; MRBrainS 43.220 s.
Verified completed-output resumes took 1.185 s and 0.397 s respectively. This is
hash verification/reuse, not algorithm acceleration. Configuration, source hash,
software versions and run journals are retained privately.

Separate 25³ synthetic component measurements (seconds, one run, no thresholds):
loading/materialization 0.001065; N4 0.010644; segmentation 0.000809;
resampling 0.001072; surface extraction 0.001491; intensity QC 0.000395;
topology QC 0.048842; NIfTI serialization 0.000797. These measure direct operations,
not stage cache serialization or human workload estimates. Stage receipts include
cache I/O/build time; the cached export node checks readiness, while immutable
publication occurs afterward. Peak RSS is a process high-water, not allocation
attributable to a single operation. No machine-specific CI performance assertion.

Reviewed the 23-case overlay contact sheet, representative full-size human and
synthetic before/after overlays, topology diagnostics and cohort performance plots.
Saved orientation/affine reports, intensity distributions, tissue overlays, DAGs,
QC/volume plots and tissue metric distributions with underlying arrays. Audit
verified 143 pickle-free, finite numeric figure NPZ files, 116 primary human PNGs,
115 subject derivative file hashes, all source/cache identities, 45 original test
files and 405 historical report files. Private artifacts are under
`reports/milestone12-validated`, `reports/milestone12-supplemental-acceptance` and
`reports/milestone12-component-performance-acceptance`. Only the aggregate receipt
`experiments/milestone12/verification.json` is committed.

## Scientific and access limits

Visual review retains strong IBSR CSF overestimation and MRBrainS extracranial
labeling/full-head confounds, including poor WM overlap in some cases. Numerical
and schema passes do not fix these anatomical errors. N4 convergence diagnostics
are recorded without claiming convergence from the iteration cap or improved
reference accuracy. Threshold foreground masks are ROI heuristics, not certified
brain extraction. Surface intersection checks are bounded and do not certify
arbitrary solids. No nonlinear registration adapter or new conductor solver exists.

Local Readme/manifest evidence and the user's authorization support only the
requested local research evaluation; they do not establish broader portal access
history, a commercial license or redistribution rights. IBSR citation/notice and
MRBrainS training-label rules are retained. Raw MRI, participant metadata, individual
results, hashes identifying source files and MRI-derived images remain Git-ignored.
No data uploads, model downloads, remote push or Milestone 13 work.

Tissue references cannot validate skull/scalp conductor boundaries, conductivity,
interface nesting, EEG/MRI coregistration, cortical source localization or clinical
utility. Independent conductor anatomy, fresh prospective cohorts, stronger
segmentation and uncertainty calibration remain unresolved.
