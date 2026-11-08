# Architecture

Soma is an installable `src/` package with array-facing numerical interfaces
independent of MNE Raw objects. MNE supplies ingestion and Morlet primitives. Dataset adapters return MNE Raw plus JSON-compatible metadata. Experiment
orchestration chooses scientific parameters and saves artifacts; visualization
consumes completed results. No global dataset is downloaded at import time.

```text
src/soma/
  core/           Signal and provenance
  datasets/       registry and explicit EEGBCI adapter
  signal/         NeuroDSP Welch, band integration, synthetic generator and lab
  eeg/            whole-record real EEG experiment
  visualization/  headless Matplotlib exports
  imaging/        MRI grids, registration, labels, meshes and candidate geometry
  source/         template/participant MNE forwards, inverse and resolution
  anatomy/        participant contracts, readiness, uncertainty and reports
  cli.py          Typer commands and readable failure codes
 tests/           unit, numerical, opt-in integration
 experiments/     executable workflow examples
 configs/         scientific parameter reference
 docs/            mathematics, data, decisions, reproducibility, roadmap
 data/raw/        original EDF files (ignored)
 data/derived/    machine-readable inspection and cache (ignored)
 reports/         per-execution figures, summaries and manifests (ignored)
```

Public APIs:

| API | Contract |
| --- | --- |
| `core.signal.Signal` | Finite real 1D samples, Hz, channel, unit, origin |
| `datasets.registry.REGISTRY` / `Dataset` | Source, selection, citation, license, sampling, callable loader |
| `datasets.eegbci.fetch` | Requested subjects × runs only; reuses cached files |
| `datasets.eegbci.recording_path` | Deterministic cache path, validates selection |
| `datasets.eegbci.event_meanings` | Run-specific annotation semantics |
| `datasets.eegbci.load_recording` | Lazy Raw and validated recording metadata |
| `signal.spectral.WelchConfig` / `welch` | Explicit Welch settings and density estimate |
| `signal.spectral.Spectrum` | Frequencies, density, metadata, peak and band power |
| `signal.synthetic.synthetic` | Six deterministic, seeded signal types |
| `signal.experiments.synthetic_spectrum` | Synthetic figures, arrays, CSV, manifest, report |
| `eeg.analysis.analyze_recording` | Motor-channel descriptive whole-record experiment |
| `visualization.spectral.plot_spectra` / `plot_segment` | Headless figure export |
| `core.provenance.manifest` / `sha256` / `write_json` | Strict JSON provenance and input identity |

`Signal.values` borrows a float64 array without copying when possible. It is not
made read-only because changing write flags would affect a caller's array. The
caller owns mutation discipline. Integer and lower-precision arrays are converted
to float64; copying then is intentional. All numerical functions reject nonfinite
data, including mutation after construction. Times allocate only when requested.
For MNE, use `Signal(raw.get_data(picks=['C3'])[0], raw.info['sfreq'], 'C3')`.
MNE channel extraction copies a single channel; the full EDF is not preloaded.

Third-party type policy: strict mypy checks application functions. MNE, SciPy,
NeuroDSP and Matplotlib lack complete compatible typing here; their missing
stubs are explicitly ignored. The MNE Raw boundary uses `Any`; runtime validation
and numerical contract tests cover this boundary. NumPy arrays are typed and
Pandas stubs are installed. This is not a claim of complete third-party checking.

CLI failures print the exception and return 1; Typer argument errors return 2.
Default outputs stay under `data/` and `reports/` relative to the working directory.
User paths are explicit overrides. Plot caches default under `data/derived/.cache`;
`MPLCONFIGDIR` and `XDG_CACHE_HOME` can explicitly override those locations.

## Milestone 2 additions

Existing loader, signal, Welch and Milestone 1 experiment interfaces are retained.
New functionality is isolated in the following modules:

| Module | API / responsibility |
| --- | --- |
| `eeg.quality` | `QualityConfig`, `quality_metrics`: finite checks and quantitative flags |
| `eeg.preprocessing` | `PreprocessingConfig`, `ProcessedRecording`, `select_eeg`, `rereference`, `design_filter`, `preprocess` |
| `eeg.geometry` | `assign_geometry`: copy, exact channel matches, meter coordinates, explicit provenance |
| `eeg.events` | `Event`, `parse_events`, `validate_events`, `event_table` |
| `eeg.epoching` | `EpochConfig`, `Trial`, `EpochSet`, `extract_trials`, `matched_rest`, `trial_table` |
| `eeg.timefrequency` | `TrialSpectra`, `trial_spectra`, `MorletConfig`, `TimeFrequency`, `morlet_power` |
| `eeg.erd` | `PowerCoordinates`, `PowerChange`, `power_change`, `lateralization` |
| `eeg.motor_imagery` | `MotorImageryConfig`, `analyze_run`, `motor_imagery`: orchestration and artifacts |
| `signal.event_locked` | `event_locked_eeg`: known seeded suppression, optional artifacts |
| `visualization.motor_imagery` | optional `plot_motor_imagery` |

Array shapes are explicitly trial/channel/frequency/time; no general framework or
xarray dependency was introduced. `ProcessedRecording` separates continuous
numeric data from the original MNE object. `EpochSet.trials` aligns accepted
samples, while `EpochSet.log` retains all proposals. Named frozen configuration
defaults are immutable. Numerical stages avoid hidden mutation; copied MNE data
are used only at ingestion, geometry and preprocessing boundaries. The new
plotting module is imported only when requested by experiment orchestration.

`analyze_run` returns both numerical objects and tables for programmatic analysis.
`motor_imagery` writes a new directory and retains per-run arrays. A failed run
can leave a partial directory, as in Milestone 1. No multi-file transaction is
claimed. The CLI JSON parser constructs explicit configuration dataclasses rather
than merging arbitrary unknown keys. Runs 4/8/12 are validated before execution.

## Milestone 3 additions

`experiments.config` builds frozen cohort configurations from strict YAML/JSON;
`experiments.cohort.run_cohort` processes selected recordings sequentially through
existing `analyze_run`, then continuous `signal.bursts`. It retains compact
per-record artifacts rather than all subjects' TFR arrays in memory. `analyze_run`
adds selected processed arrays and profiling metadata to its return mapping;
its existing signature and outputs remain compatible. Preprocessing adds an
explicit named-channel reference option while preserving average/none defaults.

`experiments.cache` provides content-addressed, checksummed run artifacts keyed
by dataset identity, input fingerprint, complete numerical settings and software
identity. No pickle or executable object cache is used. `experiments.sensitivity`
constructs a predefined one-factor-at-a-time design; it is not a parameter search.
`statistics.hierarchical` owns paired run/subject aggregation, resampling,
lateralization and optional multiplicity-corrected sign flips. `signal.cohort_synthetic`
provides repeated-measures and controlled pulse-train laboratories.
`experiments.benchmark` measures cost/cache behavior and repeated CI coverage.
`visualization.cohort` reads saved tables for auditable figures.

New CLI commands: `eeg cohort`, `eeg sensitivity`, `eeg bursts`,
`experiments cohort-synthetic`, `experiments benchmark`, and
`experiments uncertainty-validation`. Typer uses repeated `--subjects`/`--runs`
options rather than space-separated variable-length options. New commands emit
JSON summaries/errors; complete and partial cohorts retain explicit statuses,
while zero-completion commands return failure. Earlier CLI behavior is unchanged.

PyYAML is the only new runtime dependency; its types are included in development
dependencies. Statistical arrays remain NumPy/Pandas, not an additional modeling
framework. Template coordinate provenance and future measured DigMontage boundary
remain intact; no source/MRI algorithms were introduced.


## Milestone 4 extensions

`experiments/replication.py` layers sealed protocols and thin resumable per-run
checkpoints over the existing `cohort._compute` backend and content cache.
It holds one continuous recording at a time, streams combined CSVs, and loads
only small spectral feature tables for population aggregation. Existing cohort,
burst, motor-imagery and statistical APIs retain their behavior.

`statistics/inference.py` isolates independent-subject mean inference and explicit
method failure states. `statistics/robustness.py` reads saved subject/run tables.
`simulations/hierarchical.py` defines data-generating models;
`simulations/calibration.py` bounds worker count and in-flight chunk tasks.
Each dataset gets a stream derived from global seed, scenario index, N and
replicate index; data and bootstrap substreams are separate. Scheduling cannot
change the experiment. CSV chunks are atomically published before their checksum
receipts. Only verified chunks enter aggregation. Generation directories retain
prior summaries; a final atomic pointer publishes the new generation.

Cache identity includes EDF hashes, scientific settings, source code and numerical
dependencies. Calibration restricts the code digest to its inference, model and
calibration modules, permitting unrelated CLI changes without resimulation.
Reference audits are exclusively created reports; interruption leaves an explicit
partial directory, requiring a new output path.


## Milestone 5 decoding layer

`decoding/data.py` owns provenance-validated trial tensors and streamed per-record
preprocessing into a checksummed trial cache. `features.py` builds trial-local
NeuroDSP and OAS banks once. `models.py` creates fresh sklearn pipelines; public
matrix pipelines can also accept raw trial tensors. `csp.py`, `covariance.py`
and `riemannian.py` isolate validated third-party numerical methods and explicit
rank/SPD boundaries. `splits.py` validates groups, IDs and raw sample overlap.
`evaluation.py` performs subject-balanced inner selection, fresh outer fits,
adaptation, metrics and auditable partition/fit/state reporting. `workflows.py`
separates development from explicitly gated frozen prospective evaluation.
`benchmark.py` measures actual computation; `visualization/decoding.py` renders
saved predictions and diagnostic tables. Existing M1–M4 APIs remain unchanged.

All fit records reference a stored partition checksum, avoiding duplicated large
membership lists. Gzipped JSON retains every fit including failures; explicit
candidate records retain search errors. No pickle model loading is used. New
commands are grouped under `soma decode`. Trials and label-independent features
may be reused; fitted CSP, burst thresholds, scalers, tangent points and class
means are rebuilt for every permitted training partition.


## v0.6.0 source-modeling boundary

`geometry/` owns explicit metre-valued frames, rigid/affine transformations,
electrodes and source IDs. `source/template.py` owns opt-in fsaverage asset
fetching and checksummed geometry; `forward.py` delegates physical BEM fields to
MNE and binds their channel/source/orientation identities. `noise.py` owns
rank-aware projector/covariance contracts. `inverse.py` separates the independent
small SVD reference from MNE's full cortical inverse. `resolution.py` exposes
bounded PSF/CTF products and mesh geodesics. `source/power.py` batches genuine
NeuroDSP spectra. Source experiment modules orchestrate fixed simulations,
resolution and trial-wise real reconstruction; visualization has no solver role.

The native anatomical forward remains free to preserve depth-prior information;
the primary inverse is fixed signed normal. Free vector kernels rotate Cartesian
MNE output back into the stored surface basis. Source IDs are hemisphere/vertex
pairs, not inferred solely from matrix dimensions. Physical caches have atomic
completion receipts and checksums; scientific reports have code/config/version
and result hashes. Future participant anatomy adapters must explicitly supply
participant MRI transforms and validated geometry, without reusing template
coordinates as participant anatomy. See SOURCE_MODELING_METHODS.md.


## v0.7.0 MRI subsystem

`geometry.coordinates.VoxelMap` handles dimensionless identified grids without
weakening the existing metre-valued rigid `Transform`. RAS/LPS/VOXEL frame names
extend the existing enum. `imaging.Volume` owns a lazy real scalar 3D array and
RAS-m affine; `nifti` owns explicit qform/sform/unit/scaling policy. `orientation`
changes storage without interpolation; `resampling` implements explicit one-pass
pull grids. `registration` converts NiBabel RAS/(i,j,k) to SimpleITK LPS/(k,j,i),
uses mature rigid/affine optimizers and exports fixed-to-moving matrices.
`segmentation` provides conservative mask/label operations; `surfaces` delegates
to marching cubes; `mesh_quality` measures topology, intersections and containment.
`bridge.AnatomicalModel` enforces explicit subject/physical-transform provenance
before candidate MNE geometry export. Candidate geometry is not a BEM solution.

`datasets.structural` fetches only the SPM auditory T1w member via exact HTTP
ranges, requiring an explicit download request. `experiments.mri_geometry`
coordinates analytic benchmarks, real-image controlled recovery and figures;
rendering is separate. The fsaverage source modules are unchanged and remain
operational. See MRI_TO_SOURCE_ARCHITECTURE.md for future individual MRI boundaries.

## v0.8.0 participant pathway

`datasets.matched.SampleAssets` binds participant assets, digitization identities,
MRI geometry and checksums. `anatomy.contracts.IndividualModel` requires matching
source/sensor/surface subjects, measured EEG provenance and explicit head→MRI
geometry. `source.individual` prepares MNE sources/conductors and reuses the
Milestone 6 `ForwardModel`/`CorticalInverse`. Template mode remains separate.
`geometry.coregistration` supplies weighted SVD/robust fitting and labeled ICP;
`anatomy.surfaces` adds three-state readiness over the existing imaging mesh QC.
`anatomy.sensitivity` and the synthetic/participant orchestrators implement physical
perturbations, numerical derivatives and independent uncertainty controls.

Physical source/BEM/forward caches have distinct fingerprints, atomic receipts
and fail-closed checksum validation. Conductivity changes require a new BEM;
unrelated inverse settings do not. Forward keys include sensor integration
locations, projector state, transforms, source positions/normals and identities,
geometry and software/code versions. `AnatomyReport` saves nested artifact hashes,
source-tree identity and stage wall/CPU time/RSS. CLI downloads remain explicit.
See INDIVIDUAL_SOURCE_VALIDATION.md; this is conditional research, not anatomy
certification. Earlier architecture sections describe their milestone's scope.

## v0.9.0 reliability boundary

`reliability.config` seals the prospective audit settings and named random streams.
`registration` supplies asymmetric known-truth/held-out experiments and delta-method
covariance. `inverse` extracts unit-aware MNE fixed/loose/free linear kernels with
physical fingerprints and selected resolution contractions. `evidence` preserves
categorical provenance/check definitions and bounded surface/volume consistency.
`workflows` orchestrates historical reproduction, 90 inverse settings and paired
factorial simulations; `plots` saves headless figures with numeric companions.
The old M6/M8 inverse and surface APIs remain unchanged. No full dense cortical K
or new segmentation backend is introduced. Source audit commands require cached
assets; the historical inverse audit additionally requires the M8 arrays.

## v0.10.0 independent benchmark layer

`datasets.registry.REFERENCE_REGISTRY` extends factual discovery without inventing
EEG sample rates for MRI. `datasets.references` implements official selected/range
fetching, verified MINC/NIfTI conversion and original cortical VTK ingestion.
`benchmarks.segmentation` wraps existing Volume with identity/ontology contracts,
physical surfel metrics and the limited unsupervised baseline. `topology` and
`surfaces` extend existing Mesh/QC with adjacency/orientability, conservative repair
and analytic references. `offgrid` and `source_workflows` separate continuous-dipole
truth from reconstruction grids, using established MNE forwards and existing
inverse machinery. Existing data models, APIs and commands remain operational.
The new imaging/anatomy/source CLI methods are additive. No grid interpolation is
misrepresented as independent forward physics and no repaired mesh certifies anatomy.


## Milestone 11

`datasets.external_anatomy` reads bounded NRRD payloads without guessing anatomical
frames, inspects SCI reference evidence and ingests authorized MRBrainS13 training
labels. `validation.cohort` retains subjects, backend provenance, holdout integrity,
missingness and subject-level statistics while reusing Volume/LabelVolume.
`source.priors` implements ordered block covariances and sensor-space inverse
solves; `validation.source_priors` reuses M10's physical continuous-source forwards.
Existing source seal API accepts the separately sealed M11 source-priors config;
old protocol seals and results are unchanged. See MILESTONE11_RESULTS.md.
