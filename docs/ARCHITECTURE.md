# Architecture

Soma is an installable `src/` package with numerical algorithms independent of
MNE. Dataset adapters return MNE Raw plus JSON-compatible metadata. Experiment
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
