# Milestone 13 reproduction

Use Soma0.13.0 with Nilearn0.14.1. Protocol and original configurations are sealed
by configs/fmri-freeze.json; actual SPM84-volume input interpretation is a separate
sealed amendment. Set MPLBACKEND=Agg, OPENBLAS_NUM_THREADS=1 and optional writable
MPLCONFIGDIR/XDG_CACHE_HOME. All data, individual reports and derived images stay
in Git-ignored data/external, data/derived, reports or derivatives roots.

Explicit optional fetch (not performed by inspect/fit/pytest):

```python
from nilearn.datasets import fetch_spm_auditory

fetch_spm_auditory(data_dir="data/external/spm-auditory")
```

The provider permits personal education/evaluation; this fetch is not a license
for redistribution. The archive supplies raw educational data, not fMRIPrep output.
Use the explicit unvalidated-demo configuration; ordinary BIDS fits require
compatible external preprocessing, confounds, masks and spatial evidence.

```bash
soma fmri inspect --input data/external/spm-auditory/spm_auditory/MoAEpilot
soma fmri design --config configs/fmri-design.yaml --output reports/milestone13-design-cli
soma fmri fit --config configs/fmri-firstlevel.yaml --output reports/milestone13-spm
soma fmri simulate --seed 13042 --output reports/milestone13-synthetic
python experiments/milestone13/supplemental.py
pytest -o addopts=''
pytest
ruff check .
ruff format --check .
mypy --strict src/soma
python -m pip check
```

Output and input-preparation directories must be new. Design uses the specified
model config directly (its default has zero initial spikes); the first-level
SPM config explicitly overrides this with four initial spikes. The contrast CLI
reads fit_report/input-spec.json, then genuinely refits original inputs to a new
output. No executable model pickle is loaded. To reproduce the final contrast
check, set fit_report to reports/milestone13-spm in a separate private request
YAML, contrast:listening, and run soma fmri contrasts --config ... --output ... .
The generic configs/fmri-contrasts.yaml shows a different example output root.

inspect_openneuro.py downloads only public repository trees/descriptions/README,
not functional images. Its private metadata inventory documents actual release,
selected sessions/modalities and absent preprocessing. ds000114 retest requires
two explicit preprocessed session specs; the supplied placeholder config fails
with an actionable diagnostic. The multimodal command requires complete explicit
EEG/fMRI regional tables; its placeholder likewise cannot report success. These
capability boundaries are intentional, not completed real analyses.

Python use:

```python
from pathlib import Path
from soma.experiments.fmri_simulation import simulate
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.glm import contrast, fit

run, truth = simulate(seed=13042)
config = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
fitted = fit(run, config)
estimate = contrast(fitted, Contrast("task", {"task": 1.0}))
```

Run audit.py only with the final private roots, pre-work baseline ledger,
contrast-CLI result and full/offline test logs. It rechecks historical file hashes,
source identity, outputs, arrays, official schema results, exact refit equality
and completed-output verified reuse. It regenerates the aggregate verification
receipt and separate ROI/null figure. Whole-report reuse is supported by the Python
analyze(...,resume=True) API; it is not interrupted voxel-fit stage caching.
Only generic code/config/docs and aggregate software evidence are committed.
Earlier ignored development/review runs are not final acceptance results.
