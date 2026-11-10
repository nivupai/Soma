# Soma

Soma v0.17.0 adds [versioned scientific artifacts](docs/RESULT_SCHEMA_SPECIFICATION.md),
[compatibility checks](docs/SCIENTIFIC_RESULT_COMPATIBILITY.md), read-only migration
and cross-platform reproducibility evidence. See [Milestone17 results](docs/MILESTONE17_RESULTS.md).

Soma v0.16.0 provides a documented [scientific SDK](docs/SDK_OVERVIEW.md),
[eight executable examples](examples/README.md), reviewed wheel/source artifacts
and an optional local Explorer. See [installation](docs/SDK_INSTALLATION.md) and
[Milestone 16 verification](docs/MILESTONE16_RESULTS.md). Human anatomical and
fMRI interpretation limitations remain in force.

Research-oriented scientific Python foundations for EEG analysis. Milestone 1
provides explicit EEGBCI ingestion, validated one-dimensional signal arrays,
NeuroDSP Welch spectra, absolute mu/beta power, and reproducible experiments.
v0.14.0 includes template and participant-matched EEG source modeling,
structural MRI geometry, registration, conductor QC and MNE BEM sensitivity
experiments. Participant results remain conditional research computations:
independent anatomical readiness is INDETERMINATE. See
[Milestone 8 validation](docs/INDIVIDUAL_SOURCE_VALIDATION.md).

Python 3.11–3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
soma --help
soma datasets list
soma experiments synthetic-spectrum --output reports/synthetic-spectrum
soma datasets fetch eegmmidb --subjects 1 --runs 4 --data-dir data/raw
soma eeg inspect --subject 1 --run 4 --data-dir data/raw
soma eeg analyze --subject 1 --run 4 --data-dir data/raw --output reports/eeg-s001-r04
```

EEG downloads require `datasets fetch` or the explicit `eeg replicate --fetch` flag.
Template anatomy downloads require `source inspect-template --fetch`; structural
MRI uses `mri experiment real --fetch`. Repeat `--subjects` and `--runs` to
select multiple recordings. `SOMA_DATA_DIR` sets the raw data root. Output
directories must be new except resumable replication/calibration with `--resume`. Raw EDF and
reports are excluded from Git. `requirements-resolved.txt` captures the verified
environment; use it in addition to the editable install for exact versions.

```python
from soma.signal.synthetic import synthetic
from soma.signal.spectral import welch, WelchConfig

signal = synthetic("sine10", seed=42)
spectrum = welch(signal, WelchConfig(nperseg=320, noverlap=160))
print(spectrum.peak_frequency, spectrum.band_power(8, 13))
```

Validation:

```bash
pytest tests/unit
pytest tests/numerical
ruff check .
ruff format --check .
mypy src/soma
# Explicitly uses an already downloaded recording; no automatic network:
pytest -m integration tests/integration
```

See [architecture](docs/ARCHITECTURE.md), [mathematics](docs/MATHEMATICS.md),
[datasets](docs/DATASETS.md), [reproducibility](docs/REPRODUCIBILITY.md),
[verification](docs/VERIFICATION.md), and [roadmap](docs/ROADMAP.md).

## Milestone 2: event-based motor imagery

The existing Milestone 1 APIs and commands remain available. The new pipeline
adds copy-safe continuous filtering, explicit referencing, template geometry,
run-aware events with durations, logged trial rejection, valid-rest references,
trial Welch PSDs, Morlet power with support masks, and descriptive ERD/ERS.

```bash
soma eeg motor-imagery --subject 1 --runs 4 --output reports/motor-imagery-s1
# Only recordings explicitly fetched by you are loaded; this command never downloads.
soma eeg motor-imagery --subject 1 --runs 4 --runs 8 --runs 12 --output reports/motor-imagery-multi
soma eeg motor-imagery --subject 1 --runs 4 --baseline matched_rest --output reports/matched-rest
soma eeg motor-imagery --subject 1 --runs 4 --baseline none --no-plots --output reports/absolute
soma eeg motor-imagery --subject 1 --runs 4 --config configs/motor-imagery.json --output reports/configured
soma experiments event-locked --seed 42 --output reports/event-locked
soma experiments event-locked --seed 42 --artifacts --output reports/event-locked-artifacts
```

Defaults: 64-channel average reference, continuous 1–40 Hz Butterworth SOS
forward-backward filter, no notch/ICA, [1,3) s analysis, [0,4) s TFR context,
separately identified T0 rest references. The synthetic model uses no rereference
to preserve its known three-channel ground truth. All numerical settings can be
specified with the JSON configuration; unknown fields fail clearly. `--baseline`
and `--reference` override the JSON. `--no-plots` produces scientific artifacts
without importing the new plotting module.

Outputs include events/trials CSVs, QC/filter/geometry JSON, spectral features,
condition summaries, lateralization, run-specific NPZs, provenance and a report.
Figures show event timeline, template sensors, PSDs, TFR and supported ERD/ERS.
No reference is fabricated when unavailable. Runs are never silently pooled.
See [scientific methods](docs/METHODS.md) before interpreting normalized power.

## Milestone 3: cohorts, bursts and robustness

Soma 0.3.0 adds cached multi-subject replication, continuous NeuroDSP bursts,
subject-level resampling, predefined sensitivity designs and profiling. Read the
[research protocol](docs/PROTOCOL.md), particularly the small-cohort uncertainty
limitations, before interpreting estimates.

Typer lists use repeated options:

```bash
# Explicit download selection; no analysis command downloads data:
soma datasets fetch eegmmidb --subjects 1 --subjects 2 --subjects 3 --subjects 4 --subjects 5 --runs 4 --runs 8 --runs 12
soma eeg cohort --subjects 1 --subjects 2 --subjects 3 --subjects 4 --subjects 5 --runs 4 --runs 8 --runs 12 --config configs/cohort.yaml --output reports/my-cohort
soma eeg sensitivity --config configs/sensitivity.yaml --output reports/my-sensitivity
soma eeg bursts --subject 1 --runs 4 --runs 8 --runs 12 --output reports/my-bursts
soma experiments cohort-synthetic --seed 42 --output reports/my-synthetic-cohort
soma experiments cohort-synthetic --seed 42 --missing --artifacts --output reports/my-incomplete-synthetic
soma experiments benchmark --output reports/my-benchmark
soma experiments uncertainty-validation --n-subjects 5 --repetitions 200 --output reports/my-coverage
```

`--data-dir` and `--cache-dir` configure machine paths. Cohort/burst/synthetic
commands accept `--no-plots`; YAML can also set `plots: false`. Outputs must be
new directories. Cache reuse verifies checksums and input/software identity.
Partial completion is explicit JSON plus coverage tables; no successful records
returns failure. Existing Milestone 1/2 commands and APIs remain available.

Cohort figures are drawn from saved tables: subject effects, run consistency,
lateralization, burst occupancy/durations, nominal subject-bootstrap forest
intervals and retention. Sensitivity adds effect-change and missingness figures.
A nominal 95% percentile interval is not a guarantee at five subjects: the
recorded normal simulation covered only 80.5% at n=5. No population significance
or causal burst-mechanism claim is made.


## Milestone 4 — replication and statistical calibration (v0.4.0)

The [sealed research protocol](docs/REPLICATION_PROTOCOL.md) was frozen before
fetching subjects 6–35. Its checksum and timestamped freeze receipt live beside
`configs/replication.yaml`. Primary effects are equal-subject left-minus-right
mean log powers, with at least two paired runs and prespecified t intervals.
Initial-five-informed hypotheses remain exploratory.

```bash
# Uses cached EDFs; repeat --runs rather than space-separated values.
soma eeg replicate --subjects 6:35 --runs 4 --runs 8 --runs 12 --output reports/replication
soma eeg replicate --subjects 6:35 --runs 4 --runs 8 --runs 12 --output reports/replication --resume
soma eeg replicate --sensitivity --output reports/replication-sensitivity
soma eeg audit-reference --subjects 1:5 --output reports/reference-audit
soma stats calibrate --config configs/calibration.yaml --workers 4 --output reports/calibration
soma stats calibrate --config configs/calibration-smoke.yaml --workers 2 --output reports/calibration-smoke
soma stats influence --input reports/replication --output reports/influence
# Explicit expansion only; fetching is a separate opt-in:
# soma eeg replicate --subjects all --expand-all --fetch --output reports/expanded
```

`current.json` points to an immutable aggregation generation. Completed record
checkpoints and Monte Carlo chunks are checksum-validated on resume. Parameter,
source code or environment mismatches reject reuse. Incomplete/failed recording
attempts retain their identities and errors. No command implicitly fetches all
109 subjects. Original EDFs and original M1–M3 outputs remain intact.

See [statistical methodology](docs/STATISTICS.md),
[Milestone 4 results](docs/MILESTONE4_RESULTS.md), and
[verification](docs/VERIFICATION.md). All figures derive from saved CSV tables.


## Milestone 5 — decoding and covariance geometry (v0.5.0)

The [sealed decoding protocol](docs/DECODING_PROTOCOL.md) defines nine sensor-space
models, grouped evaluation and a reserved prospective cohort. Development uses
subjects 1–35; subjects 36–65 require a separate frozen configuration and command.
See [decoder methods](docs/DECODING_METHODS.md) for assumptions and leakage boundaries.

```bash
# Repeat --runs using the existing Typer convention.
soma decode within-subject --subjects 1:35 --runs 4 --runs 8 --runs 12 --output reports/decoding-within
soma decode cross-subject --subjects 1:35 --runs 4 --runs 8 --runs 12 --output reports/decoding-cross
soma decode adaptation --subjects 1:35 --output reports/decoding-adaptation
soma decode synthetic --seed 42 --output reports/decoding-synthetic
soma decode benchmark --output reports/decoding-benchmark
# Efficient complete development suite: one shared trial/feature bank, including null refits.
soma decode development-suite --output reports/m5-development-final
# Requires completed development and a passing receipt for the exact code/environment:
soma decode freeze-heldout --verification configs/decoding-verification.json --development reports/m5-development-final --output configs/decoding-frozen.yaml
# Explicit prospective access only after freezing; --fetch is a separate opt-in.
soma decode evaluate-heldout --subjects 36:65 --config configs/decoding-frozen.yaml --output reports/decoding-heldout --fetch
```

All learned transformations remain inside fresh training pipelines. Trial-local
NeuroDSP features and OAS covariances can be shared across folds; scalers, burst
thresholds, CSP, tangent references and class means cannot. Output directories
are new; failed folds retain error records, and cached trial files are validated
by EDF/code/parameter/dependency identity and checksums. Fitted model objects are
never loaded from untrusted pickle files. Main decoding dependencies are
scikit-learn and pyRiemann, with MNE CSP. No deep learning or anatomical source
reconstruction is implemented.


Milestone 5 completed 105 development and 90 prospectively reserved recordings,
all nine frozen decoders and all three evaluation modes. The suite passes 312
tests, including all 256 baseline tests unchanged. Full model tables, calibration,
adaptation, numerical checks and limitations are in
[Milestone 5 results](docs/MILESTONE5_RESULTS.md) and the
[prospective freeze record](docs/PROSPECTIVE_DECODING_FREEZE.md).

The commands illustrate the staged workflow; supplied frozen files are immutable
and already exist. Use a new report directory for reproduction. Verification
receipts must describe actual successful checks for the current code/environment;
the original receipt, command logs and generation script are preserved under
`configs/decoding-verification.json` and `reports/m5-verification`. A deterministic
rerun of the completed held-out sample is not another prospective validation.


## Milestone 6: template EEG source modeling

Read the sealed [source protocol](docs/SOURCE_MODELING_PROTOCOL.md),
[methods](docs/SOURCE_MODELING_METHODS.md), and
[measured validation](docs/SOURCE_MODELING_VALIDATION.md).

```bash
export MPLBACKEND=Agg
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
soma source inspect-template --fetch  # explicit large fsaverage download
soma datasets fetch eegmmidb --subjects 1 --runs 4 --runs 8 --runs 12
soma source inspect-template
soma source forward --subject 1 --run 4 --output reports/my-source-forward
soma source simulate --config configs/source-simulation.yaml --output reports/my-source-simulation
soma source inverse --subject 1 --runs 4 --runs 8 --runs 12 --output reports/my-source-inverse
soma source resolution --config configs/source-resolution.yaml --output reports/my-source-resolution
soma source benchmark --output reports/my-source-benchmark
```

The verified demonstration is in `reports/milestone6-verified/` (local, excluded
from Git); the standalone fresh-forward benchmark is in
`reports/milestone6-final/benchmark/`. The fixed-normal forward is 64×1,284,
rank 63. Fifty new source tests supplement the 312 unchanged baseline tests.
Ordinary CI is offline; cached-template tests require an explicit integration run.

All real maps use individual-trial source power, with an evoked comparison using
the same inverse kernel. MNE currents and dimensionless dSPM estimates retain
separate units. Anatomical templates, normalized channel labels, and good numerical
conditioning do not establish individualized motor-cortex localization.


## Milestone 7: structural MRI geometry and anatomical candidates

Use the [MRI geometry methods](docs/MRI_GEOMETRY_METHODS.md),
[registration methods](docs/MRI_REGISTRATION_METHODS.md),
[surface methods](docs/MRI_SURFACE_MODELING.md),
[MRI-to-source boundary](docs/MRI_TO_SOURCE_ARCHITECTURE.md), and
[validation results](docs/MRI_VALIDATION.md).

```bash
export MPLBACKEND=Agg
export OPENBLAS_NUM_THREADS=1
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
soma mri experiment synthetic --seed 42 --output reports/my-mri-synthetic
soma mri experiment real --dataset spm-auditory --fetch --output reports/my-mri-real
soma mri inspect --input data/raw/mri/spm-auditory-T1w.nii
soma mri validate --input data/raw/mri/spm-auditory-T1w.nii
soma mri resample --input input.nii.gz --reference reference.nii.gz --output reports/my-resample
soma mri register --fixed fixed.nii.gz --moving moving.nii.gz --mode rigid --output reports/my-registration
soma mri surfaces --mask mask.nii.gz --output reports/my-surface
soma mri benchmark --input data/raw/mri/spm-auditory-T1w.nii --output reports/my-mri-benchmark
```

Downloads require the explicit `--fetch` on the real experiment. The SPM adapter
retrieves only the anatomical ZIP member using HTTP byte ranges, not the functional
time series. Dataset terms permit personal education/evaluation; see the recorded
source terms before other uses. Raw anatomy and full reports remain excluded
from Git. All result directories must be new; source files are never overwritten.

Internal physical coordinates use metres; NIfTI storage and SimpleITK units are
converted explicitly. Ambiguous qform/sform metadata requires an explicit policy.
Label resampling requires `--labels --order 0`. Registration matrices map fixed
RAS to moving RAS; optimization completion does not establish anatomical accuracy.

The verified local reports are in `reports/milestone7-complete/`. The real threshold
foreground surface fails topology checks and is **not BEM ready**. Synthetic
closed nested shells pass their scoped geometric checks. No production brain/
tissue segmentation, individual EEG/MRI coregistration, new BEM solver or
Milestone 8 implementation is included.

## Participant MRI/EEG research workflow (v0.8.0)

```bash
soma anatomy inspect --dataset mne-sample --fetch  # explicit full sample archive
sh experiments/milestone8/run.sh reports/my-m8-run
soma anatomy inspect --dataset ds000117 --discover  # metadata only
soma anatomy inspect --dataset ds000117 --subject sub-01
```

The synthetic command runs offline: `soma anatomy experiment synthetic --seed 42
--output reports/my-synthetic-head`. Real commands never fetch implicitly.
The [sealed protocol](docs/INDIVIDUAL_HEAD_MODEL_PROTOCOL.md),
[disclosed amendment](docs/INDIVIDUAL_HEAD_MODEL_AMENDMENT.md),
[coregistration methods](docs/COREGISTRATION_METHODS.md),
[BEM checks](docs/BEM_GEOMETRY_VALIDATION.md) and
[uncertainty methods](docs/ANATOMICAL_UNCERTAINTY.md) define scope and limitations.

## Model reliability (v0.9.0)

With explicitly cached sample assets and the original M8 reports:

```bash
sh experiments/milestone9/run.sh reports/my-reliability-run
```

The new source audit/calibration commands explain the historical current
attenuation through W L, compare signed MNE currents with separately labeled
normalized statistics, and quantify paired uncertainty interactions. Anatomical
evidence remains INDETERMINATE. See [Milestone 9 results](docs/MILESTONE9_RESULTS.md).

## Independent references and off-grid validation (v0.10.0)

```bash
soma mri references list
soma mri references fetch --dataset brainweb
soma mri references fetch --dataset mindboggle-101  # selected subject, cohort transport
sh experiments/milestone10/run.sh reports/my-m10-run
```

The methods study compares actual provided tissue/manual cortical references,
checks topology and conservative repair, and evaluates continuous dipoles against
separate reconstruction grids. Downloads are explicit; cortical labels are not
skull/scalp truth. See [Milestone 10 results](docs/MILESTONE10_RESULTS.md).


Milestone 11 adds external SCI computational-reference inspection, authorized-local
human tissue adapters, subject-disjoint cohort evaluation and block source-prior
calibration. [Results and incomplete criteria](docs/MILESTONE11_RESULTS.md) distinguish
missing human references from completed synthetic experiments. The authorized
version assertion now targets 0.11.0; every other earlier test is unchanged.
See [verification](docs/VERIFICATION.md).

```bash
soma mri references inspect --dataset sci-head
soma mri benchmark-tissues --config configs/tissue-benchmark.yaml --output reports/m11-tissues
soma anatomy compare-conductors --config configs/conductor-comparison.yaml --output reports/m11-conductors
soma source priors --config configs/source-priors.yaml --output reports/m11-priors
soma source grid-priors --config configs/grid-priors.yaml --output reports/m11-grid-priors
soma experiments anatomical-holdout --config configs/anatomical-holdout.yaml --output reports/m11-holdout
```

Each output directory must be new. SCI acquisition is explicit through
`python experiments/milestone11/fetch_sci.py`; registered datasets and segmentation
model weights are never automatically fetched. Tissue reports retain missing-data
status until authorized labels are supplied. Reproduce all actions with
`sh experiments/milestone11/run.sh` after activating the environment.


Milestone 11 human MRI integration is documented in the
[human-reference methods addendum](docs/HUMAN_TISSUE_REFERENCE_METHODS.md) and the
[results addendum](docs/MILESTONE11_RESULTS.md#human-mri-reference-integration-addendum).
User-provided local IBSR and MRBrainS training references now support a separate
frozen evaluation; earlier missing-data reports remain historical and unchanged.
Raw data, participant records and all MRI-derived images stay outside Git.

```sh
soma mri inventory-human --output reports/human-inventory-new
soma mri benchmark-human-tissues --inventory reports/human-inventory-new/inventory.json --phase development --output reports/human-development-new
soma mri benchmark-human-tissues --inventory reports/human-inventory-new/inventory.json --phase external --output reports/human-external-new
```

Run `python experiments/milestone11-human/run.py` for ordered reproduction with
an explicit code/input freeze before external evaluation. No test-partition label
contents, downloads, new models or conductor validation are involved.


## Milestone 12 anatomical MRI pipelines

Soma now provides PyBIDS discovery, an eleven-stage serial MRI DAG, optional N4,
explicit masking/resampling, backend-neutral segmentation, geometry/ontology QC,
private BIDS derivatives and content-derived stage recovery. Python examples are
in [BIDS integration](docs/BIDS_INTEGRATION.md); contracts are in the
[accepted architecture record](docs/MRI_PIPELINE_ARCHITECTURE.md).

```bash
soma mri bids-inspect --input /local/bids
soma mri pipeline --input /local/bids --participant-label 01 --config configs/mri-pipeline.yaml --output derivatives/soma --dry-run
soma mri pipeline-legacy --dataset ibsr --data-root data/external/ibsr --config configs/mri-pipeline.yaml --output reports/ibsr-pipeline
soma mri validate-derivatives --input reports/ibsr-pipeline/derivatives/soma
```

All 18 IBSR and five permitted MRBrainS training cases reproduce the fixed prior
metrics exactly; their derivatives pass the official offline validator. Anatomical
and conductor readiness remain INDETERMINATE. Full tests: 690 pass, one historical
0.11.0 version assertion fails as explicitly requested by the user. See
[measured results and limits](docs/MILESTONE12_RESULTS.md) and
[reproduction](experiments/milestone12/README.md). No raw MRI or identifiable
outputs belong in Git. No remote push or Milestone 13 is included.


## Milestone 13 task-fMRI and spatial interfaces

Soma0.13 adds explicit4D BOLD records, PyBIDS task ingestion, Nilearn first-level
OLS/AR(1), design/contrast validation, FDR maps, ROI/surface utilities and guarded
regional EEG/fMRI comparison. See [methods](docs/FMIRI_GLM_METHODS.md),
[spatial requirements](docs/FMIRI_SPATIAL_MODELING.md) and
[reproduction/Python examples](experiments/milestone13/README.md).

```bash
soma fmri simulate --seed 13042 --output reports/fmri-synthetic
soma fmri inspect --input /local/bids
```

The real SPM auditory demonstration is explicitly raw educational data with
incomplete preprocessing evidence. ds000114 retest and ds000117 matched EEG/fMRI
results remain unavailable without appropriate preprocessing/transforms. Statistical
maps are custom reports; supported mask derivatives pass official BIDS validation.
No clinical/anatomical certification or joint multimodal model is claimed. See
[measured results and limitations](docs/MILESTONE13_RESULTS.md). Historical M12
reports retain their original test counts; the current full suite is green.


## Milestone14 preprocessing audit and reliability

Soma0.14 adds audited fMRIPrep imports, measured-confound policies, ITK nonlinear
transform evidence, independent GLS references, AR2 calibration and subject-level
reliability/ICC. Full suite:815 passed; offline:798 passed,17 deselected.

```bash
soma fmri audit-preproc --config configs/fmri-audit.yaml --output reports/preproc-audit --dry-run
soma fmri calibrate --config configs/fmri-calibration-validation.yaml --output reports/calibration
```

Only one ds000114 participant's two raw motor runs/T1w references were fetched.
Compatible preprocessing is unavailable, so no real pilot/cohort was modeled.
Complete acceptance remains false. Synthetic calibration retains excess family
rejections under feasible AR models; numerical correctness is not an inference
certificate. See [actual results](docs/MILESTONE14_RESULTS.md),
[import requirements](docs/FMIRI_PREPROCESSING_AUDIT.md) and
[reproduction](experiments/milestone14/README.md). No raw MRI/private results are
committed, no push, and no Milestone15 work.

## Soma Explorer (v0.15.0)

The local React/TypeScript workstation and FastAPI scientific API are in
`apps/explorer` and `services/explorer_api`. It includes deterministic synthetic
EEG, MRI, source and fMRI views and explicit adapters for permitted local data.

```sh
.venv/bin/python -m pip install -e '.[dev,explorer]'
npm --prefix apps/explorer ci
.venv/bin/python -m uvicorn services.explorer_api.app:app --host 127.0.0.1 --port 8000
# In another terminal:
npm --prefix apps/explorer run dev
```

Open `http://127.0.0.1:5173`. No medical data download or preprocessing is launched.
Human fMRI confirmation and unavailable preprocessing/retest remain restricted.
See [user guide](docs/EXPLORER_USER_GUIDE.md),
[architecture](docs/EXPLORER_ARCHITECTURE.md),
[security](docs/EXPLORER_SECURITY.md) and
[results](docs/MILESTONE15_RESULTS.md).

## Soma 0.18.0 workflow provenance

Explicit scientific DAGs support verified caching, selective invalidation, atomic
publication/resume and a read-only interactive Explorer. Start with
`python -m examples.workflow_provenance` or `soma workflow --help`. See
[workflow specification](docs/WORKFLOW_PROVENANCE_SPECIFICATION.md) and
[Milestone 18 results](docs/MILESTONE18_RESULTS.md).

### Research protocol replay (0.19.0)

Use `soma.sdk.protocol` or `soma protocol` / `soma replay` for immutable local
scientific declarations, structural amendments and controlled descriptive replay.
Explorer's Protocols page compares registered execution evidence without running
workflows. See [the protocol specification](docs/RESEARCH_PROTOCOL_SPECIFICATION.md)
and [Milestone 19 evidence](docs/MILESTONE19_RESULTS.md). Local seals are not
independent preregistration, and synthetic replay does not establish human validity.

### Human data audit (0.20.0)

`soma.sdk.human`, the `data`/`human-pilot`/`registration` CLI groups and Explorer's
Data Audit view add scoped identity/session checks and content-bound use evidence.
Adapters inspect explicit cached data only. Unknown rights or missing preprocessing
produce blocked records, not fabricated human scientific results. See
[Milestone 20](docs/MILESTONE20_RESULTS.md) for actual coverage and remaining gaps.

### Research readiness — v0.21.0

Read-only immutable registration attachments, sealed evidence bundles, preprocessing/QC and session gates extend existing protocols. Real preprocessing and permission gaps stay blocked. See [Milestone21 results](docs/MILESTONE21_RESULTS.md).
