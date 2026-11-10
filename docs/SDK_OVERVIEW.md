# Soma v0.16 SDK overview

The supported namespace is `soma.sdk`, with explicit domain imports. It adds no
alternative numerical engines. Existing implementation imports and CLI commands
remain compatible. Domain functions are direct aliases unless a stricter boundary
helper is listed below. The root namespace imports only the version.

Architecture plan and delivered boundaries:

1. Small domain facades over existing MRI, EEG, source and fMRI modules.
2. Manifest extensions for declared semantics, with conservative comparison checks.
3. Explicit wheel packages: `soma` and the compatible `services` Explorer gateway.
4. Deterministic examples, artifact inspection and fresh noneditable installations.
5. Independent scientific, quality, packaging, Explorer and privacy CI jobs.

The scientific dependency set remains intact: MRI/EEG/fMRI were not split into
extras because current CLI and shared modules import these libraries together.
`explorer` remains optional; the core package does not require FastAPI. Importing
`soma.sdk.explorer` is safe without it; creating the app gives an actionable error.

API inventory:

| Capability | Supported SDK boundary | Existing implementation |
|---|---|---|
| MRI load/metadata/geometry | imaging | imaging.nifti, volumes, validation |
| Spatial transforms | imaging.Frame, Points, Transform, ras_lps | geometry |
| Registration/resampling | imaging | imaging.registration, resampling |
| Tissue benchmark | imaging.LabelVolume, score | benchmarks.segmentation |
| Surface QC | imaging.Mesh, mesh_quality, extract_surface | imaging.surfaces, mesh_quality |
| EEG identity/events/trials | eeg | datasets.eegbci, eeg.events, epoching |
| PSD/bursts/time-frequency | eeg | signal.spectral, bursts, eeg.timefrequency |
| Forward/inverse | source | source.forward, inverse, noise, resolution |
| Design/GLM/contrast/ROI | fmri | fmri.design, glm, spatial, inference |
| Manifest/identity | provenance | core.provenance plus SDK checks |
| Synthetic examples | synthetic | existing phantoms/simulators |
| Installed local gateway | explorer | services.explorer_api |

Workflow orchestrators, dataset downloaders, private reference adapters, experiment
configuration/freezing, anatomical readiness decisions and preprocessing backends
remain research/internal APIs. They can still be imported at their existing paths,
but are outside the v0.16 SDK compatibility promise. A supported interface is not
a claim that its model has been validated on human anatomy.

See [API reference](SDK_API_REFERENCE.md), [installation](SDK_INSTALLATION.md),
[examples](../examples/README.md) and [results](MILESTONE16_RESULTS.md).

## Research protocols (0.19.0 addendum)

`soma.sdk.protocol` adds immutable declarations/seals, structural revision comparison,
registered graph conformance, three replay modes, drift and append-only local history.
See CONTROLLED_WORKFLOW_REPLAY.md and `examples/research_protocol.py`. Replay is
synthetic/descriptive; it grants no confirmation or cross-environment cache reuse.
