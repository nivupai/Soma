# Reproducibility

Install with Python 3.11 or 3.12 in a virtual environment and `pip install -e
'.[dev]'`. `requirements-resolved.txt` records the actual verified Python 3.12
macOS environment, excluding the editable project path. To reproduce versions,
install that file then install the project editable. Platform-specific wheels
and Python versions can still affect results. CI tests both supported Python
versions using declared compatibility ranges; the local resolved file is an
execution record rather than a universal cross-platform lock.

Every experiment creates a new directory with `exist_ok=False`. Existing output
is never silently reused or replaced, even after a failed run. Choose a fresh
output path. Failures can leave an incomplete directory; a successful run has
its report and manifest. No atomic multi-file transaction is promised.

Manifests contain source dataset/version/file, subject/run (null for synthetic),
scientific parameters, sampling frequency, selected channels, PSD conventions,
units, random seed, execution UTC timestamp, Python and installed library
versions, application version, Git revision and working-tree state when available.
Machine paths are isolated under `paths`. EEG manifests include a SHA-256 of the
original EDF. This is identity tracking, not verification against a remote signed
checksum. Raw files remain unchanged; derived arrays and summaries are separate.

Synthetic signals use a fresh `numpy.random.default_rng(seed)` for each generator
call. The six-signal experiment uses the same seed intentionally, so noisy and
burst cases share the background realization. Exact bitwise random results are
only promised for the recorded compatible environment, not arbitrary future
NumPy versions. Determinism tests compare repeated calls within that environment.

`spectra.npz` holds `frequencies` (Hz, shape F), `density` (V²/Hz, shape C×F), and
`channels` (Unicode labels, shape C). Load with `numpy.load(..., allow_pickle=False)`.
CSV powers are V² and retain full numeric precision. PNG is presentation only;
never extract quantitative results from a log-axis plot. `recording.json` retains
EDF event samples and annotation durations; manifests retain estimator settings.

Offline tests use short synthetic arrays and mocked MNE loading. They cannot
prove that a live server, a changed EDF, or every future third-party release is
compatible. `pytest -m integration tests/integration` is opt-in and reads only an
already cached S001R04 file, skipping if absent. CI never fetches EEG files.

Git revision is null if no commit exists, or if a wheel installation is outside a
repository. Dirty state is explicit. Initial pre-commit verification artifacts
can therefore record a null revision; post-commit verification should use fresh
output directories to record the committed revision. Generated files are ignored.

Spectral PNGs show 0–40 Hz (or the available range if smaller) and six decades
below the largest plotted density. This display limit hides numerical roundoff
near pure-tone zero bins; the saved NPZ density arrays are untouched.
