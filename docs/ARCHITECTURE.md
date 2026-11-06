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
  imaging/        documented future boundary only
  source/         documented future boundary only
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
