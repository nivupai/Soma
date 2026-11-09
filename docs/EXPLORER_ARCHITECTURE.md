# Soma Explorer architecture

Milestone15 adds a local workstation to the existing scientific library. It does
not replace numerical methods or historical artifacts. `services/explorer_api/`
contains FastAPI/Pydantic contracts, allowlisted resource registration, bounded
Soma adapters and one local job worker. `apps/explorer/` contains React19,
TypeScript, Vite7, canvas/SVG viewers and a lazily loaded Three.js renderer.

The service runs from the repository root. Soma remains the owner of NeuroDSP
Welch/bursts, MNE time-frequency, NIfTI/physical geometry, fMRI simulation/GLM,
phantom meshing, source waveforms and selected resolution operators. JavaScript
only presents returned data and handles interaction. No scientific estimator is
reimplemented in JavaScript.

## Data flow

An ignored operator configuration maps opaque IDs to allowed-root-relative files.
The catalog lists explicit subject/session/run identities. Requests validate IDs,
resource kinds, real resolved paths and bounds. The adapter returns typed data,
units, frame, interpretation state, input fingerprint, software/code provenance
and nearby limitations. Cached inputs are scoped by registry/identity and
invalidated on file signature changes. No browser path argument or automatic
dataset download exists. Discovery is curated, paginated and offline rather than
an indiscriminate scan of participant directories.

React's typed reducer owns page/mode/dataset/window/channels/voxel/source. Dataset,
mode and laboratory changes reset incompatible selections; old asynchronous
responses are aborted and cannot populate a new identity's panels. One voxel
controls all MRI planes. EEG trial annotations update the shared native-sample
analysis window; PSD/TFR/bursts use that window, not decimated display samples.
Source selection drives a 3D marker, time course and available PSF/leakage results.

## Rendering choice

Three.js was selected over vtk.js for bounded triangular surfaces/point sets,
standard orbit/pan/zoom controls, ray picking and small integration surface.
The API sends slices rather than full MRI volumes, so vtk.js volume rendering
would add weight without helping this implementation. Three.js is lazy-loaded;
the initial application and 3D chunk are separately measured. Renderer geometries,
materials, controls, event listeners and WebGL contexts are released on unmount.
Rendering is event-driven, not an always-running animation loop.

The synthetic mesh comes from Soma's analytic ellipsoid. The cached template
adapter reads existing source-space `use_tris`, verifies hemisphere vertex IDs
and MRI frame, applies Soma's rigid MRI-to-head transform and checks every point
against the sealed source artifact. This reduced cortical display is not the BEM
conductor tessellation; numerical geometry is never modified. No new BEM is built.

## Jobs and scientific boundaries

One worker accepts only bounded EEG analysis jobs (one running, one queued).
Cancellation is cooperative between numerical stages and suppresses publication;
it does not forcibly interrupt a native library call. Each job has a UUID, status,
coarse progress, failure state and an atomic private manifest. No shell, arbitrary
Python, distributed queue, cohort job or automatic expensive computation exists.

All new human and feasible-AR results are descriptive. There is no confirmatory UI
switch; the fMRI API rejects explicit confirmatory requests. Missing human
fMRIPrep/retest outputs remain NOT_AVAILABLE. Demo results remain EXPLORATORY;
passing numerical tests does not establish anatomical or clinical validity.

Implementation references: [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/),
[Three.js](https://threejs.org/docs/), [Vite](https://vite.dev/guide/) and
[Playwright web servers](https://playwright.dev/docs/test-webserver).
Installed versions are pinned in the lockfile/verification receipt; current online
manuals are not treated as evidence of the installed software version.
