# Installing and reproducing Soma v0.16.0

Python 3.11–3.12. Install from your authorized private checkout or a reviewed local
wheel; no public package publication or data download is part of this workflow.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install '.[dev,explorer]'
.venv/bin/python -m build
.venv/bin/python scripts/inspect_distributions.py dist/soma_neuro-0.16.0-py3-none-any.whl dist/soma_neuro-0.16.0.tar.gz
.venv/bin/python scripts/verify_install.py dist/soma_neuro-0.16.0-py3-none-any.whl --env .venv-wheel
.venv/bin/python scripts/verify_install.py dist/soma_neuro-0.16.0.tar.gz --env .venv-sdist
.venv/bin/python scripts/verify_install.py . --env .venv-source
.venv/bin/python -m scripts.run_sdk_examples
```

Every verification environment is new, noneditable, without system site packages,
and probes imports from an unrelated temporary cwd. Core is checked before the
optional Explorer extra. It resolves real runtime dependencies, runs CLI help/list,
all eight examples, installed API probes, and pip check. Resolved dependency lists
and private execution receipts go to ignored `reports/milestone16/`.

The scientific dependency graph is unchanged. Core includes the existing MRI/EEG/
fMRI stack; `explorer` adds FastAPI/Pydantic/Uvicorn/HTTPX and `dev` adds test/build
tools. No external preprocessing executable, model weights or datasets are installed.
The wheel includes `soma`, the compatible `services` API gateway, `py.typed` and the
small preserved descriptive-only policy resource and a content-hashed synthetic
calibration excerpt used by the demo experiment browser. The sdist includes reviewed
source, examples, tests, documentation, configurations and the unchanged calibration
verification record required by the resource-integrity regression; no local registrations,
raw data, reports, original Git history, backups, frontend dependencies or builds.
Existing experiment CLI workflows can still require a repository config/protocol
and explicit cached resources; they are not advertised as standalone SDK recipes.

Offline provisioning requires an existing platform/Python-specific wheelhouse:

```sh
.venv-wheel/bin/python -m pip freeze --exclude soma-neuro > reports/milestone16/runtime-pins.txt
.venv/bin/python -m pip wheel -r reports/milestone16/runtime-pins.txt 'hatchling==1.27.0' --wheel-dir reports/milestone16/wheelhouse
.venv/bin/python scripts/verify_install.py dist/soma_neuro-0.16.0-py3-none-any.whl --env .venv-offline --wheelhouse reports/milestone16/wheelhouse
```

Retain the wheelhouse, artifact hashes and resolved pins privately. This supports
offline installation, not a universal cross-platform lock. Build isolation still
needs the pinned Hatchling backend; include its transitive wheels for offline sdist
builds. Byte reproducibility is tested by rebuilding under a fixed SOURCE_DATE_EPOCH.
Source archives and wheels are inspected separately. Scientific calculations can
vary across numerical libraries/platforms; CI asserts tolerances, not exact timings.
Linux Python3.11/3.12 CI and local macOS Python3.12 evidence are reported separately.

## First local Explorer run

```sh
soma-explorer --port 8000
# In a frontend checkout, separate terminal:
npm --prefix apps/explorer ci
npm --prefix apps/explorer run dev
```

Open http://127.0.0.1:5173. The catalog offers synthetic EEG/MRI/source/fMRI data
without registration. The installed SDK provides the API; the React frontend is a
separate local build, not bundled in the wheel. The source viewer remains lazy.
`python -m examples.explorer` is an offline demo smoke check.

To register permitted local files, follow EXPLORER_USER_GUIDE.md and set
SOMA_EXPLORER_CONFIG to an ignored local allowlist JSON before starting the server.
No raw path can be selected through an API request. Roots, symlinks and file bounds
remain validated. Servers bind to loopback; no telemetry or public deployment was
added. Human fMRI confirmation remains unavailable because independent preprocessing
and inferential calibration evidence is insufficient. Unavailable data are not
silently replaced with synthetic participant results.
