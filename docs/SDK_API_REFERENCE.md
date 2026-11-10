# SDK API reference and compatibility

All imports below are explicit. The domain modules expose no wildcard API. Python
3.11 and 3.12 are supported. Existing module locations remain available; no
historical scientific assertions or experimental results were changed.

| Operation / public import | Inputs → outputs | Preconditions / errors / limits |
|---|---|---|
| `imaging.load_nifti` | Path + explicit frame/policy/kind → lazy Volume | NIfTI1/2; coded forms/units checked; ambiguous geometry rejected by default |
| `imaging.save_nifti` | Volume, new Path → None | never overwrite; derived mm header; shear qform uncoded |
| `imaging.validate_volume` | Volume, check_data=False → diagnostics dict | metadata-only default does not certify finite intensities |
| `Volume.grid.to_world/to_voxel` | n×3 indices / Points → Points / ndarray | RAS metres; voxel indices dimensionless; no clipping |
| `imaging.require_same_space` | two Volumes + subject/space → None | explicit identities in both metadata dicts plus same grid; no registration certification |
| `imaging.inspect_volumes` | iterable of Paths → ordered diagnostics list | strict load policy, fail on first error; no parallel or hidden downloads |
| `imaging.resample_labels` | label Volume, reference, explicit pull Transform → Volume | nearest only; RAS metres; labels finite/nonnegative integers |
| `imaging.resample` | Volume, reference + order/transform → Volume | order 0/1/3; labels require 0; repeated interpolation rejected by default |
| `imaging.register` | reference/moving Volumes + RegistrationConfig → RegistrationResult | SimpleITK local optimum; returned reference-to-source mapping; inspect QC |
| `imaging.LabelVolume`, `score` | identified label volumes → per-label metric dict | equal subject/space/grid/ontology; SDK additionally rejects undeclared label IDs; absent metrics may be None |
| `imaging.Mesh`, `mesh_quality` | metre Points + triangular faces → QC dict | topology/intersections/orientation; volume None unless valid under checks |
| `eeg.recording_metadata` | cache root, EEGBCI subject/run → metadata/events dict | no fetch; handle closed; may include local provenance, keep private |
| `eeg.load_recording` | same → (MNE Raw, metadata) | caller must close Raw; no preprocessing/download |
| `eeg.parse_events`, `event_table` | Raw + explicit identity / events → events tuple / DataFrame | run-specific meanings, seconds; no invented trials |
| `eeg.extract_trials`, `trial_table` | ProcessedRecording, EpochConfig / EpochSet → EpochSet / table | retain acceptance/rejection and half-open sample windows; see EEG guide |
| `eeg.eeg_spectrum` | Signal in V, optional WelchConfig → Spectrum | rejects non-voltage units; alias `welch` retains general-signal unit support |
| `eeg.morlet_power`, `trial_spectra` | EpochSet + config → named array dataclasses | finite trials, frequency/Nyquist and full-support edge masks |
| `eeg.calibrated_detector`, `intervals` | filtered 1D volts, Hz, thresholds, seconds / bool mask → mask / intervals | filtering/calibration/valid exposure remain caller responsibilities |
| `source.Tikhonov` | matrix, lambda2, optional NoiseModel → solve/kernel/diagnostics | small toy diagnostic; caller-defined units; nonnegative regularization |
| `source.build_forward`, `CorticalInverse` | explicit Template/channels/cache / ForwardModel+covariance → operators | cached anatomy only unless explicit fetch elsewhere; matching identities/reference required |
| `source.Resolution` | inverse kernel + forward → selected PSF/CTF | bounded selections; no dense cortical matrix |
| `fmri.FunctionalRun`, `load_run` | image/timing/identity/events/confounds/mask → validated run contract | mm/sec headers, coded geometry, no automatic preprocessing certification |
| `fmri.build_design`, `fit` | run, ModelConfig → design/diagnostics, Fit | full rank; explicit raw educational mode; config specifies model/HRF/nuisance |
| `fmri.contrast` | Fit, Contrast, optional InferencePolicy → Estimate | named estimable two-sided contrast; existing guard always evaluated |
| `fmri.fixed_effects` | distinct compatible Estimates → maps/metadata | within subject only; same estimand/space/mask/effect scale; no population inference |
| `fmri.align_roi`, `roi_estimates` | SpatialMap / explicit SpatialChain → aligned ROI / rows | label mapping, subject/space required; no inferred registration; ROI covariance unavailable |
| `provenance.result_metadata` | explicit fingerprint/method/units/identity/estimand/state/source → JSON dict | extends existing manifest; strict finite JSON; never authorizes confirmation |
| `provenance.require_comparable` | two SDK metadata dicts → None | same schema/version/method/units/identity/estimand/space/state/parameters; conservative, no statistical pooling |
| `provenance.read_manifest`, `write_json` | Path / Path+JSON → dict / None | read rejects nonfinite/nonobject JSON; writer creates exclusively |
| `provenance.array_fingerprint`, `sha256` | finite array / file → lowercase SHA256 | shape/dtype/order-aware array bytes; file streamed; hashes do not anonymize participants |
| `explorer.create_app` | none → FastAPI app | optional Explorer dependencies; explicit environment registry; local service only |

Domain dependencies are the existing declared NumPy/SciPy/MNE/NeuroDSP/NiBabel/
SimpleITK/scikit-image/Nilearn stack. No install or import downloads a dataset.
Registration, smoothing, preprocessing and inverse hyperparameters are explicit;
read the underlying function signatures for complete keyword defaults. New helper
`score` accepts the existing `tolerances_mm` and `valid_mask` keywords unchanged.
Result classes retain native structures; this release does not wrap every array in
a competing universal result object. Use manifest extensions when exporting a
comparable result, and retain the original method-specific metadata alongside it.

NumPy typing portability fixes add explicit float64 return conversion and Python
float scalars at existing boundaries. Formulas are unchanged. The SDK root is
lightweight; domain imports load their scientific dependencies.

## Versioned results (v0.17)

`soma.sdk.results` exports create_result, validate_result, inspect_result, save_result,
load_result, verify_integrity, verify_provenance, compare_results, require_compatible,
convert_units, upgrade_schema and migrate_legacy. All paths are explicit Path
objects. Metadata inspection does not read arrays; numerical loading verifies
linked bytes. See RESULT_SCHEMA_SPECIFICATION.md, ARTIFACT_INTEGRITY.md and
SCIENTIFIC_RESULT_COMPATIBILITY.md for complete contracts and limits.

## Workflow provenance (0.18.0)

`soma.sdk.workflow` exports Artifact, Stage, Graph, WorkflowError, Registry,
Operation, Executor, builtins, example, changed, identities, content, digest,
invalidation, opaque_subject and redact_export. Create an explicit graph, validate
with the code-owned registry, inspect dependencies/lineage, plan, run or resume.
Executor.run accepts input_root, snapshotted in-memory inputs, cancellation/fault
callbacks, a run-journal path and optional previous Graph for invalidation evidence.
Cache internals remain private. See WORKFLOW_PROVENANCE_SPECIFICATION.md and the
public examples/workflow_provenance.py. CLI `soma workflow --help` lists inspect,
validate, plan, run/resume, explain-cache, lineage, verify and example generation.

## Protocol API (0.19.0 addendum)

`Protocol.from_dict`, `Snapshot.from_dict`, `seal/read_seal/write_seal`, `amend`,
`compare_protocols`, `graph_for`, `conformance`, `plan`, `run`, `compare`,
`read_execution/write_execution`, `history/append_history`, `historical_evidence`
and `redact_export` are exposed by `soma.sdk.protocol`. Validation raises
`ProtocolError`; methods return immutable records or copied finite JSON summaries.
See the protocol guides for exact mode preconditions and scientific limits.

## Human API (0.20.0 addendum)

`Identity`, `Selection`, `PermissionEvidence`, `create_identity`, `pseudonym`,
`session_match`, `chronology`, `validate_cohort`, `eeg`, `mri`, `bids_fmri`,
`check_permission`, `template`, `freeze_cohort`, `conformance`, `plan`, `run`,
`graph_for`, `read_execution`, `compare`, `export_audit`, `RegistrationProvider`,
`inspect_registration` and `verify_registration` are public through `soma.sdk.human`.
Creation of declared identity metadata is distinct from source-adapter validation.
Actual planning requires a consistent private mapping key and fresh source evidence.
CLI groups: `data inspect/validate-identity/permissions/protocol-check`,
`human-pilot plan/run`, `registration inspect/verify`. Registration network access
requires `--network`; raw datasets are never fetched by these commands.

## Milestone 21 addendum

`soma.sdk.readiness` exports typed evidence bundles, immutable attachment verification, preprocessing imports/audits, session audits, readiness gates and native read/write helpers. `execution_readiness` rechecks live inputs; reports do not authorize execution. Existing SDK contracts remain. See [evidence bundles](RESEARCH_EVIDENCE_BUNDLES.md) and the fictional `examples/research_readiness.py`.

### CLI readiness reference (0.21.0)

The existing Typer groups are extended with `registration verify-attachment`,
`evidence inspect/verify`, `preprocessing audit`, `sessions validate` and
`research readiness`. Each command accepts explicit local files/roots. Provider
retrieval requires `--network`. No command executes fMRIPrep or a shell. See
[command syntax and policy](HUMAN_DATA_READINESS_GATES.md).
