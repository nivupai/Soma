# Soma Explorer scientific API

Start from the repository root with the `explorer` extra installed. FastAPI's
`/openapi.json` describes actual Pydantic models. The default CSP blocks CDN-based
Swagger/Redoc scripts; use this JSON schema and these local API documents. The frontend's typed
client is `apps/explorer/src/api/client.ts`; HTTP/schema tests verify core contracts.
Errors expose a bounded scientific-input diagnostic, not local paths or tracebacks.

| Route | Returned scientific data |
|---|---|
| `GET /api/catalog` | Registered datasets, subject/session/run identities, state and availability |
| `GET /api/eeg/{id}/metadata` | Channels, Hz, duration, V, reference, events and quality flags |
| `GET /api/eeg/{id}/window` | Bounded bin means/min/max, exact sample bounds, timestamps and display-only marker |
| `GET /api/eeg/{id}/analysis` | Native-sample Welch V²/Hz, mu/beta V², Morlet V² and burst intervals |
| `GET /api/volumes/{id}` | Grid, full affine in mm, axis codes, spacing, frame, intensity and label metadata |
| `GET /api/volumes/{id}/slice` | Plane pixels/labels, voxel/world position and full pixel-to-world matrix |
| `GET /api/sources/{id}/mesh` | Bounded display triangles/points/electrodes, frame, amplitude color data and QC |
| `GET /api/sources/{id}/series` | Selected source time course, units, position and available selected PSF/leakage |
| `GET /api/fmri/{id}` | Descriptive model/design/events, available ROI/residual metadata and policy |
| `GET /api/experiments` | Paginated configured receipts, metrics, parameters, compatibility, hashes and figures |
| `POST /api/experiments/compare` | Comparison only with identical units/estimand/frame/processing declarations |
| `GET /api/experiments/{id}/export` | Existing sanitized result as CSV/JSON; CSV formula prefixes escaped |
| `GET /api/experiments/{id}/figures/{index}` | Explicitly configured bounded PNG, never arbitrary file access |
| `GET /api/qc` | Structured current readiness and unavailable human analyses |
| `POST/GET/DELETE /api/jobs[/{id}]` | Validated submission, polling and cooperative cancellation |

Scientific responses use `Result[T]`: dataset identity, SYNTHETIC flag, structured
state, warnings, provenance and typed payload. Units are explicit in field names.
The states include VALIDATED_NUMERICAL, DESCRIPTIVE_ONLY, EXPLORATORY,
INDETERMINATE, INVALID and NOT_AVAILABLE; the demo does not label itself clinical
or anatomically validated. Raw BOLD may expose header metadata but cannot become a
validated contrast map. There is no map-generation endpoint for unpreprocessed
human BOLD. `inference=confirmatory` is rejected.

## Bounds and reductions

EEG:1–8 channels, windows0.1–30s, analysis2–30s, at most2048 display points/channel;
recordings at most256 channels/2048Hz. Display bins preserve min/max and means;
analysis consumes original samples. Fractional requests round to the native
sample grid, and returned analysis timestamps use the consumed sample origin. One-second Welch Hann segments with50%
overlap and 3-cycle Morlet8–30Hz are explicit; burst thresholds3/5µV and minimum
3 cycles are window-local, exploratory, not calibrated against participant rest.
The TFR guard is reported beside the result. Channel analysis currently uses the
first selected channel; other traces remain display channels.

MRI:32M voxel cap, explicit3D input (raw4D BOLD is metadata-only), maximum128 pixels
per slice dimension with nearest voxel display stride. Canonical reorientation is
lossless axis permutation/reflection, not a registration. Label overlays require
identical canonical grid/affine. Unknown units/conflicting geometry are rejected;
any operator-declared unit override is visible in warnings. No silent resampling.

Source archives:64MiB decoded ZIP cap, finite numerical arrays only, no pickle;
source matrix at most10,000×10,000 within the byte limit; time coordinates strictly
increase. Curated operators/geometry must match sealed hashes; optional template
connectivity additionally matches vertex order and transformed positions. Selected
PSFs use Soma's existing Resolution class, never a dense full resolution matrix.

Files:1GiB cap, JSON metadata4MiB, approved PNG4MiB,8 figures maximum, tables4MiB,
design at most2000×64. Requests16KiB. Bounded caches and two concurrent small EEG
analyses prevent accidental computation bursts. These are local research limits,
not a claim that the API is suitable for internet exposure.

## M35 head scene and uncertainty overlay

| Route | Returned data |
|---|---|
| `GET /api/head-scenes` | Summaries of servable head scenes (only `demo-synthetic-head`) with readiness |
| `GET /api/head-scenes/{head_id}` | `HeadScene`: nested layers, sensors, cortical-surface sources, readiness |
| `GET /api/head-scenes/{head_id}/uncertainty` | `SourceUncertaintyOverlay`: per-source scalar + interval |

Any other `head_id` is 404; `m32-*` identities are additionally rejected (403) by the
existing private-anatomy middleware. Models live in `services/explorer_api/head_scene.py`.

`HeadScene` (`contract = "soma.explorer.head-scene/1"`), units mm, frame
`synthetic_head_RAS_mm`:

- `readiness`: `VALIDATED | QC_ONLY | NOT_READY`, the short form of Soma's
  `AnatomicalLevel` (`readiness_status` holds the full value, `readiness_reasons` the
  limitations from `soma.anatomy.head_models.classify_anatomy`).
- `geometrically_valid` (closed edge-manifold shells, finite coordinates, per-ray
  nesting, sensors on scalp, sources inside cortex; details in `geometry_checks`) and
  `anatomically_validated` are independent fields. The model rejects
  `anatomically_validated` without `VALIDATED` readiness, and on any synthetic head.
- `layers[]`: `{name: scalp|outer_skull|inner_skull|cortex, label, vertices_mm, faces}`.
- `sensors[]`: `{label, position_mm}`; `sources`: `{kind: "cortical_surface",
  positions_mm, normals, scalar_name, scalar_units, scalar}` with aligned lengths.
- `synthetic`, `redistributable`, `private_mri_used` (always `false`), `generator`, `warnings`.

The demo head is generated in code from icosphere shells (scalp 95, outer skull 89,
inner skull 83, folded cortex 77 mm along +y, shared ellipsoidal axes) with idealized
10-20 sensors and a 162-point synthetic cortical source space. It is not MRI-derived,
so `classify_anatomy` returns `NOT_READY` although its geometry is valid.

`SourceUncertaintyOverlay` (`contract = "soma.explorer.source-uncertainty-overlay/1"`):

```json
{"head_id": "demo-synthetic-head", "quantity": "localisation_error", "units": "mm",
 "statistic": "mean", "interval": "confidence_interval", "confidence_level": 0.95,
 "n_sources": 162, "mean": [...], "lower": [...], "upper": [...],
 "origin": "MOCK_FIXTURE", "fixture": true, "warnings": ["MOCK FIXTURE: ..."]}
```

Validation requires one value per source and `0 <= lower <= mean <= upper`, and
`fixture` must equal `origin == "MOCK_FIXTURE"`. The current values are a
deterministic placeholder (worse for lower sources) standing in for M34
localisation-error results, which do not exist yet; M34 should publish
`origin = "M34_RESULT"` with the same shape. The browser re-validates the overlay
against the head's source count and refuses to colour sources with a mismatch.
