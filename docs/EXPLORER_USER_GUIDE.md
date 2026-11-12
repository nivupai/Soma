# Soma Explorer user guide

From the repository root, use the existing Python 3.11/3.12 environment:

```sh
.venv/bin/python -m pip install -e '.[dev,explorer]'
npm --prefix apps/explorer ci
```

The frontend lockfile includes a project-local Node22 runtime because the
pre-existing Node22.9 was below Vite's minimum. npm scripts prepend the local
binary directory. Alternatively use a supported system Node. Installing packages
and the Playwright browser is a separate online setup step; scientific tests and
the demo never download datasets. No FreeSurfer/fMRIPrep execution is needed.

Start the API from the repository root:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/soma-mpl \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv/bin/python -m uvicorn services.explorer_api.app:app \
  --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
npm --prefix apps/explorer run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the local service. Actual schemas are at `http://127.0.0.1:8000/openapi.json` and in
`docs/explorer-openapi.json`. CDN-based Swagger/Redoc scripts are blocked by the
local CSP; these interactive documentation pages are not part of the offline UI. Stop both
terminal processes to stop the application. Do not use `--host 0.0.0.0`.

## Demo and local data

Synthetic demo works without medical datasets. It uses Soma's seeded EEG,
asymmetric MRI phantom, analytic source currents and task fMRI simulation/GLM.
Every demo view is marked SYNTHETIC/EXPLORATORY. Toggle Local data to use only
resources explicitly selected by the server operator. An empty local registry
shows unavailable resources, not fabricated results.

Set `SOMA_EXPLORER_CONFIG=configs/explorer.local.json` **before starting** the API.
The ignored file has this shape (replace paths with your authorized locations):

```json
{
  "roots": {"recordings": "/absolute/authorized/eeg"},
  "entries": [{
    "id": "my-eeg", "kind": "eeg", "label": "Authorized EEG recording",
    "root": "recordings", "file": "recording.edf", "run": "4",
    "subject": "local-study-code", "session": "visit-1",
    "provenance": "As-recorded reference; not artifact-cleaned"
  }]
}
```

Supported local adapters: EDF EEG; explicit3D NIfTI anatomy or effect map;
source NPZ bundles containing estimate/times and optional sealed geometry,
operators and cached MNE source-space connectivity; JSON experiment receipts and
approved PNGs. See Entry's OpenAPI-independent server schema in
`services/explorer_api/registry.py`. Unknown MRI units require a deliberate
`spatial_units_override`; the warning is shown. Never guess units or frame names.

For the already permitted cached resources used in milestone verification, an
explicit optional setup is:

```sh
.venv/bin/python -m experiments.milestone15.configure_local
```

It writes an ignored allowlist; it does not download or modify recordings. It is
specific to the existing repository cache, not a general dataset downloader.

## Working in the laboratories

EEG:select a dataset, channels and window; navigate with arrows/slider or select a
trial. PSD/TFR/bursts analyze the first selected channel at original sampling.
MRI:click any slice or use I/J/K sliders. All crosshairs/world coordinates update.
Use windowing, label/opacity, zoom and Shift-drag pan; orientation stays explicit.
Source:orbit/zoom/pan, toggle layers, click a source or enter its index. Review
frame/provenance and available resolution diagnostics before interpretation.
fMRI:inspect the available task effect, design and diagnostics. Human contrasts
are descriptive; raw BOLD and missing preprocessing cannot become valid maps.
Experiments:filter receipts, inspect definitions, export CSV/JSON and compare only
compatible results. Explicit EEG job submission is separate from browsing.

The right inspector shows context, interpretation, warnings and provenance. It can
be resized where supported, hidden and restored. Theme switches between dark and
light; only theme preference is saved in localStorage. Keyboard controls and
collapsed navigation retain accessible names.

## Verification

```sh
.venv/bin/pytest -m ''
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --strict src/soma services
.venv/bin/python -m pip check
npm --prefix apps/explorer run test
npm --prefix apps/explorer run typecheck
npm --prefix apps/explorer run lint
npm --prefix apps/explorer run format
npm --prefix apps/explorer run build
```

Install the matching browser once with
`apps/explorer/node_modules/.bin/playwright install chromium --only-shell`.
Then `npm --prefix apps/explorer run e2e` starts/reuses local servers. Local-data
E2E coverage is explicitly skipped when the optional allowlist is absent; all
synthetic checks remain offline. Set `CAPTURE_EXPLORER=1` only for deliberate
synthetic screenshot recapture; participant views are never captured into docs.

## Versioned scientific artifacts

Register an experiment entry pointing to result.json under an explicit permitted
root. Arrays must remain in its arrays/ directory. The browser displays schema,
validation and migration status; invalid/future/corrupt records show reasons and
no figures. Original payloads are never edited. Comparisons of versioned records
use the scientific compatibility engine; legacy four-field declarations retain
their narrower historical meaning. Metadata on the wire is sanitized; checksums
identify the original artifact, not a sanitized display copy. Schema validation
does not grant statistical or anatomical validity.

## Workflow lineage

Open Workflows to inspect synthetic or explicitly registered saved DAGs. Navigation
is read-only and does not start computations. Use node selection, lineage direction,
node search, zoom/pan, fit and keyboard navigator. Cache labels are recorded
observations, not fresh verification. See WORKFLOW_EXPLORER.md.

## Protocols (0.19.0 addendum)

Open **Protocols** to inspect four local synthetic declarations without executing
them. Empty execution histories are explicit. To prepare actual synthetic histories,
run `scripts/prepare_protocol_explorer.py --root reports/protocol-histories --config
reports/protocol-explorer.local.json`, optionally with `--base` for an existing
ignored allowlist. Start Explorer with that explicit SOMA_EXPLORER_CONFIG.

Select a registered protocol/revision and two execution records. EXACT rejects
method changes; EXPLORATORY requires an explicit amendment. Inspect snapshot/QC,
conformance, deviations, drift values and upstream/downstream lineage. Numerical
plots cover aligned selected summaries only. No page action executes a workflow.
Local seal status is never displayed as external preregistration.

## Research data audit (0.20.0 addendum)

**Data Audit** shows dataset-scoped participant/session structure, task/modality,
use-evidence status, protocol eligibility, execution readiness, missing preprocessing,
deviations and registration warnings. The default is an explicitly fictional,
unexecuted metadata fixture. Reading it never starts science or contacts providers.

Register actual ignored native human execution artifacts explicitly as `human-audit`
entries under allowed roots. Optional `metadata_file` can reference a local registration
receipt; it is labeled not revalidated, never automatically external preregistration.
Audit responses contain selected metadata/lineage, not metric arrays, images, private
mappings or keys. Scoped pseudonyms still require controlled access; the configured
local boundary is not a general publication authorization.

## Milestone 21 addendum

Data Audit now shows immutable registration claims, bundle integrity/review, preprocessing and session requirements with per-gate READY/BLOCKED/INDETERMINATE/NOT_APPLICABLE states. Configured `human-readiness` entries read metadata-only native results. Historical receipts are not revalidated by GET. The session table preserves explicit labels and nulls; no override/run/upload controls are provided.

## v0.22 EEG decoding benchmark

The existing Experiments workbench includes an EEG benchmark receipt selector and
prespecified sensitivity selector. Default preview is NOT_RUN, with no invented
human performance. A configured `eeg-benchmark` registry entry points to the native
aggregate `result.json`, never the private execution/subject table. Existing allowed
roots and explicit local configuration rules still apply.

The panel shows frozen protocol identity, cohort/trial coverage, five methods in
both evaluation modes, subject bootstrap intervals, missing counts, anonymous
subject-distribution bins and expandable leakage/adaptation/null diagnostics.
GET requests never launch a benchmark. Historical reuse, conditional uncertainty,
invalid human nominal permutation inference and supervised adaptation remain
visible. Participant identifiers and local paths are not exposed.

## v0.23 external EEG audit

The existing Experiments workbench shows an external EEG section alongside the
M22 benchmark. It displays source/target, license/permission, exact/harmonized/refit
mode, model compatibility, zero observed human coverage, domain-shift availability
and blocked outcomes. Default evidence contains no human accuracy. An explicitly
configured `external-eeg` registry entry may point to a validated native aggregate
receipt. GET never fits a model, downloads data or overrides permissions. No
participant-level predictions, model arrays or local paths are exposed.

## v0.24 prospective model archive

Experiments includes a model-release selector, protocol/cohort/family evidence,
fitted-state verification and separately labeled source validation. An unselected
preview does not claim a human model. Configured `model-archive` entries point only
to reviewed metadata summaries, never private manifests or arrays. External
acquisition and human external accuracy remain unavailable. No model fit or signal
download runs when opening the panel.

## v0.25 frozen external validation

Experiments separates acquisition approval, scientific compatibility, immutable
source-model identity and actual human coverage. Configured `external-validation`
entries accept aggregate receipts only. Blocked execution displays no human accuracy.
Fictional results carry SYNTHETIC TEST ONLY and separate numerical outcomes.
HTTP views are GET-only; opening the panel cannot acquire data or launch inference.

## v0.26 source uncertainty

Source Models includes a separate known-truth synthetic four-shell experiment.
Choose an inverse method/error source to compare baseline and perturbed maps,
3D peak error, dispersion, grid floor and physical amplitude availability. Crosses
mark truth and amber marks the peak. Maps use their own magnitude scales; the
XY projection is not a cortical reconstruction of the selected human resource.
All nine rejected configuration rows remain listed. The API is GET-only.
