# Milestone15 results — Soma Explorer0.15.0

A functional locally hosted workstation now connects the existing Soma library
to a typed FastAPI service and React/TypeScript application. This is an additive
milestone from294f794; scientific methods, public Soma APIs,851 baseline tests and
historical reports are preserved. No push, public deployment or Milestone16.

## Working application and actual data coverage

The API and frontend were run on localhost8000/5173 and exercised in headless
Chromium, not accepted on build output alone. The application has dark/light
modes, a responsive laboratory sidebar, scientific inspector, warnings near
results, keyboard-accessible parameter controls, resizable inspector and
coordinated typed selections.

- EEG:real cached PhysioNet EEGBCI EDF recording loaded, with channel windows,
  sampling/reference/voltage units and motor-imagery events. Native-sample
  NeuroDSP Welch, Morlet power, mu/beta summaries, exploratory bursts, trial
  selection and display envelopes work. No recording was downloaded or cleaned
  implicitly; raw reference/quality limitations remain visible.
- MRI:one permitted cached ds000114 T1w loaded. All three planes, actual affine,
  anisotropic aspect, neurological labels, crosshairs, voxel/world coordinates,
  intensity windowing and zoom/pan work. Synthetic aligned labels/opacity are
  demonstrated; no real segmentation is fabricated when none is registered.
- Source:one existing sealed template-source bundle loaded. Its1284 source points,
  2560 reduced cortical triangles and64 electrodes share a verified MNE head frame.
  Hemisphere IDs and MRI-to-head coordinates match the historical bundle. Source
  selection, current time courses, leadfield singular values, selected PSF/leakage
  and registered historical regularization figures are inspectable. No forward or
  inverse solver was launched. Numerical BEM geometry is unchanged.
- fMRI:one historical synthetic task effect artifact loaded under descriptive
  policy. Its missing NIfTI unit declaration was rejected until an explicit mm
  override was configured using the original generator's affine; the original
  image was never edited and the override is shown. The demo separately performs
  Soma's small synthetic GLM and displays a signed design matrix, effect maps,
  ROI mean and residual metadata. Human fMRIPrep/retest remain NOT_AVAILABLE;
  zero new human GLMs or reliability results were created.
- Workbench:curated immutable receipts, parameter/software/provenance inspection,
  hashes, approved figures, compatibility rejection and CSV/JSON export work.
  Explicit bounded EEG jobs have progress, cancellation, failure handling and
  atomically persisted hashed results/manifests under ignored private output.

All four demo modalities are deterministic and visibly SYNTHETIC/EXPLORATORY.
Committed screenshots are actual synthetic application captures; no participant
image, individual local screenshot, raw recording or local allowlist is committed.
The default app works without cached medical datasets. The optional local fixture
helper only registers already permitted local resources.

## Verification

| Check | Actual result |
|---|---|
| Full Python suite |892 passed;103 warnings;851 baseline +41 new API tests |
| Ordinary offline Python |875 passed;17 integration tests deselected |
| Frontend component/state/color tests |14 passed |
| Playwright E2E |8 passed, no local coverage skipped in this run |
| Strict mypy |191 source modules, including the service |
| Python lint/format |Ruff checks pass |
| TypeScript, frontend lint/format/build |Pass |
| Dependencies |pip check and npm dependency tree pass |

The aggregate verification receipt records exact times and preservation counts.
Existing tests were not weakened or rewritten. Initial version-check failures
were stale installed editable metadata, resolved by reinstalling0.15.0; assertions
continue to compare package/source/project metadata. New version provenance tests
also use package metadata rather than an obsolete fixed release.

Tests verify native-analysis/display independence, units/events, affine
permutation/reflection/anisotropy, pixel-to-world mapping, aligned labels, wrong
units/grids, root/traversal/symlink rejection, cache invalidation, sealed geometry/
receipt/figure checksums, CSV safety, interpretation states, policy refusal,
compatible comparisons, capacity/cancellation and hashed job publication.
Browser checks include source WebGL, source selection, MRI physical aspect and
picking after zoom, shared crosshairs, event-linked panels, local artifacts,
exports/jobs, light mode and narrow-screen keyboard navigation. Export regression
checks also preserve all201 test rows and source metrics while removing private
path fields; metadata is bounded by file size rather than silently truncated.

Visual QA caught and corrected two scientific display issues: viewport-relative
sizes had stretched anisotropic MRI, and the power colormap had hidden regressor
signs in the GLM matrix. Their fixes have browser/color regression checks. The final crosshair drawing
was also centered on voxel centers rather than pixel boundaries; picking and
reported physical coordinates were already correct. Six
final synthetic captures were inspected for geometry, labels, units, warnings and
layout; see `EXPLORER_VISUALIZATION.md`.

## Measured costs

Darwin/arm64, thread limits1; in-process TestClient measurements include request
handling and JSON serialization but exclude real network latency. Nine calls per
case; one first-call measurement and eight warm repetitions. These are observed
costs under current host load, not timing acceptance thresholds.

| Operation | Warm median ms | Warm p95 ms | Response bytes |
|---|---:|---:|---:|
| Cached EEG window | 7.59 | 8.09 | 37,100 |
| Cached EEG PSD/TFR/bursts | 3.35 | 3.64 | 46,278 |
| Cached T1w slice | 7.26 | 7.72 | 50,330 |
| Template cortical display | 8.82 | 12.48 | 236,453 |
| Source time course / selected PSF | 6.13 | 6.58 | 49,134 |
| Experiment discovery | 4.36 | 4.69 | 64,456 |

API process peak RSS **427.42MiB** includes scientific
libraries and cached images, not incremental request allocation. Browser synthetic
MRI navigation was **17ms**, source selection
**19ms**, cold source view readiness
**1108ms** and twelve orbit steps
**204ms**. JavaScript heap estimate
**29.4MB**; median animation frame interval
**16.70ms**. Browser timing uses wall-clock
UI readiness on headless Chromium and is not a numerical-computation benchmark.
The heap estimate excludes GPU and other renderer-native allocations.

The initial JavaScript bundle is about84KB gzip; the lazy 3D chunk about133KB gzip.
Vite still warns that the uncompressed3D chunk exceeds500KB. It is isolated from
the initial viewer but remains a startup/memory cost. Full timing/payload/version
receipts are in `experiments/milestone15/`.

## Security, reproducibility and remaining limits

Allowed roots/opaque identities, per-access realpath checks, strict local origins/
hosts, streamed16KiB body cap, bounded windows/arrays, no arbitrary filesystem or
execution endpoint, sanitized exports and private atomic job outputs are tested.
No analytics/telemetry exporter is configured. This has no internet/multi-user
authentication boundary and must remain bound to localhost. Path safety and
numerical validation do not establish anatomical or clinical validity.

Current adapters are deliberately curated, not a universal importer or automatic
BIDS cohort crawler. Each registered fMRI map is one contrast; additional maps
require additional explicit entries. No validated human preprocessing, anatomical
registration QA, human retest, cohort ICC or human confirmatory result is supplied.
There is no UI policy bypass. Imported missing design/ROI/confound metadata stays
unavailable. The demo ROI is a descriptive whole-mask mean, not an inferential ROI
standard error.

MRI planes remain voxel-aligned, including obliquity; full affine coordinates are
reported, while arbitrary shear angles are not geometrically resliced. Display
meshes are reduced source-space connectivity, not full cortical/BEM meshes. No
anatomical truth is inferred from an inverse reconstruction. EEG bursts use fixed
window-local thresholds, not participant-rest calibration. Source3D camera
navigation uses mouse/touch gestures; scientific source/voxel/channel selections
and parameter controls have keyboard alternatives. Jobs support only bounded EEG
analysis; cancellation is cooperative, and there is no generic solver launcher.

Interactive Swagger/Redoc HTML is not provided offline: the CSP blocks its CDN
scripts. Typed OpenAPI JSON and local Markdown API documentation remain available.

The CI configuration installs optional API dependencies and adds frontend/browser
checks. Package/browser installation is a separate setup phase; ordinary tests
never fetch scientific datasets. The updated GitHub workflow is committed locally
but was not executed remotely because no push was performed.
