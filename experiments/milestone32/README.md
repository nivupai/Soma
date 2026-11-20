# M32 MRI-derived anatomy

Design/seal were committed before final processing. Results are public-safe aggregates;
participant data, coordinates, meshes, reference overlays, lead fields and input hashes
remain under ignored local storage. Obtain authorized data independently and inspect
local metadata/permissions before running these commands from the repository root:

```sh
python -m scripts.run_mri_head_models --local-output reports/milestone32/reproduction
python -m scripts.summarize_mri_head_models reports/milestone32/reproduction --output reports/milestone32/public-review
python -m scripts.audit_mri_geometry32 reports/milestone32/reproduction --output reports/milestone32/dataset-geometry.json
python -m scripts.audit_mri_surface_displacement32 reports/milestone32/reproduction --output reports/milestone32/decimation-displacement.csv
python -m scripts.prepare_mri_head_viewer reports/milestone32/reproduction --output reports/milestone32/private-view --config reports/milestone32/viewer.local.json
SOMA_LOCAL_ANATOMY_VIEWER=1 SOMA_EXPLORER_CONFIG=reports/milestone32/viewer.local.json python -m soma.sdk.explorer
```

The SDK binds loopback. Anatomy is disabled by default; direct loopback clients only,
no forwarded headers or remote origins. Never proxy or publish the opted-in service.
Public CI runs only `scripts.mri_head_repro`, independently checked synthetic coordinate
and voxel-prior fixtures; it never downloads MRI. See `docs/MILESTONE32_RESULTS.md` and
the reference/QC/verification documents. Numerical failures and missing anatomy truth
are explicit. No M33 factorial or M32 automatic merge.
