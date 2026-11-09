# Milestone14 reproduction

Baseline0312635; original protocol/config checksums are in milestone14-freeze.json.
The validation amendment seals fresh seeds15142–15241 separately; development
checks/smoke used14142 onwards. No original report is regenerated as new evidence.

```bash
# Explicit bounded fetch only; not called by fit/audit/pytest:
python experiments/milestone14/fetch_pilot.py --fetch
soma fmri audit-preproc --config configs/fmri-audit.yaml --output reports/milestone14-audit
soma fmri pilot-retest --config configs/retest-pilot.yaml --output reports/milestone14-pilot
soma fmri cohort-retest --config configs/retest-cohort.yaml --output reports/milestone14-cohort
soma fmri sensitivity --config configs/fmri-sensitivity.yaml --output reports/milestone14-sensitivity
python experiments/milestone14/laboratory.py
soma fmri calibrate --config configs/fmri-calibration-validation.yaml --output reports/milestone14-calibration
pytest -o addopts=''
pytest
ruff check .
ruff format --check .
mypy --strict src/soma
python -m pip check
```

Set MPLBACKEND=Agg, writable MPLCONFIGDIR/XDG_CACHE_HOME and OpenBLAS/OMP/ITK
threads1; LOKY_MAX_CPU_COUNT=1 makes the bounded AR2 setup explicit. run_final.py
records the actual commands/expected exit codes. In this environment the first
four real workflows intentionally return1/status unavailable, because required
external preprocessing is absent. They do not fit raw motor images. Dry-run
flags inspect configuration/data without writing outcomes or launching jobs.

Output/input directories are exclusive. Repeating these exact paths intentionally
fails; choose new private roots for a new experiment and update orchestration paths
together. The fetch is exactly two motor BOLD/two T1w files for one selected
participant, checks annex digests and metadata version, and never fetches others.
No fMRIPrep, container or template installation is performed. Real execution of
external_preprocessing requires a preinstalled executable, verified local resources
and explicit offline launcher; it is not part of final execution here.

The laboratory reuses an explicitly synthetic test fixture, whose source hash is
recorded; it is not real fMRIPrep preprocessing. Its10-subject cohort is separately
simulated and ROI labels are analytic, not anatomical ground truth. All medical
inputs, participant identities, detailed rows, figures and private hashes remain
in ignored data/external, data/derived or reports roots. Only aggregate receipts
and generic code/config/docs are committed.

Audit.py requires the pre-work private baseline ledger, final outputs, raw annex
receipts and final full/offline logs. It verifies unchanged baseline reports/tests,
source/output hashes, finite pickle-free arrays, seeded rows, independent GLS
arithmetic and explicit unavailable-human criteria before updating verification.json.
