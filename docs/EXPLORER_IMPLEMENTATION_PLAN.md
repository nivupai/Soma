# Soma Explorer implementation plan — Milestone 15

Baseline294f794, Soma0.14.1,851 tests. Existing repository has no frontend/service
infrastructure. Preserve scientific source APIs, baseline tests and report files.

1. Record baseline source/test/artifact hashes and verify ignored medical roots.
   Add an optional FastAPI/Pydantic/Uvicorn service and separate React/TypeScript/
   Vite application. Keep simulation and numerical work in existing Soma Python.
2. Define typed bounded catalog, EEG window/analysis, volume metadata/slice,
   mesh/source, fMRI, experiment/QC and job contracts. Explicit server config maps
   opaque IDs to allowed-root-relative files; reject traversal/symlink escapes,
   unknown IDs, oversized arrays and cross-dataset selections. Localhost-only,
   restrictive CORS/origin/host checks; no arbitrary file or execution endpoints.
3. Create deterministic synthetic demo from existing Soma EEG, anatomical and
   fMRI generators. Make provenance and inference state inseparable from results.
   Adapter coverage includes actual cached EDF/NIfTI and curated existing source/
   fMRI artifacts; unsupported formats/results report unavailable explicitly.
4. Build bounded EEG traces/events, PSD/TFR/burst/band/trial views; coordinated
   affine-aware orthogonal slices with labels/segmentation/windowing; Three.js
   geometry/source inspection with QC and provenance. Assess lightweight Three.js
   versus larger vtk.js; preserve numerical meshes, cap display geometry.
5. Build workbench/validation/settings, compatibility-checked comparison and
   CSV/JSON export, typed centralized selection/reset rules. Add explicit bounded
   cancellable local jobs; navigation never launches heavy numerical experiments.
6. Exercise demo and permitted local EEG/MRI/source/fMRI data through actual API
   and browser. Add endpoint/security/coordinate/numerical/state/component/E2E
   tests. Run851 baseline tests, full API suite, strict mypy, Ruff, dependency
   checks, TS, frontend lint/format/unit and Playwright. Ordinary CI stays offline.
7. Measure API/window/slice/mesh/source/discovery serialization and browser frame/
   memory costs. Capture and visually inspect actual running screenshots; retain
   only synthetic screenshots in Git. Document measured limits and unavailable
   human preprocessing/retest; never bypass14.1 policy.
8. Version0.15.0, final preservation/privacy audit, explicit local commit:
   `feat: build interactive Soma research explorer`. No push or Milestone16.
