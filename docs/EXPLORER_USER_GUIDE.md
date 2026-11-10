# Soma Explorer user guide

From the repository root, use the existing Python3.11/3.12 environment:

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
