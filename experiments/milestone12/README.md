# Milestone 12 reproduction

The accepted ADR and configs are sealed by `configs/milestone12-freeze.json`.
Use the installed v0.12.0 dev environment, including PyBIDS and the optional
local official validator. Set `MPLBACKEND=Agg`, `OPENBLAS_NUM_THREADS=1` and
`ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1`. No commands download MRI or weights.

```bash
soma mri benchmark-pipeline --config configs/pipeline-benchmark.yaml --output reports/milestone12-validated
python experiments/milestone12/supplemental.py
python experiments/milestone12/performance.py
python experiments/milestone12/audit.py
pytest
pytest -o addopts=''
ruff check .
ruff format --check .
mypy --strict src/soma
python -m pip check
```

Outputs must be new; existing run roots are intentionally exclusive. Supplemental
paths are declared in the scripts and use a dedicated initially empty cache so
interruption counts measure that experiment alone. For another execution, choose
new ignored roots and update the orchestration paths together; do not overwrite
this run. The audit requires the private baseline ledger captured before work and
existing frozen M11 reports; those are intentionally not public test fixtures.
The aggregate verification receipt contains no participant identities or image
hashes. Detailed input/output hashes, validator warnings, per-subject tissue tables,
figure arrays and MRI-derived images remain private and ignored.

Both pytest commands intentionally return nonzero solely because the user directed
that the old 0.11.0 version assertion remain unchanged while targeting 0.12.0.
See `docs/MILESTONE12_RESULTS.md` for measured results and acceptance limitations.
Earlier development runs in other ignored roots are not acceptance results.
