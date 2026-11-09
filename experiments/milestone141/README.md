# Milestone 14.1 reproducibility

Run from the repository root with the existing editable development environment.
All `reports/`, raw MRI and patient derivatives are ignored. The committed JSON
contains aggregate synthetic results and readiness status only. No raw MRI,
patient images, identifying individual hashes or participant-level results belong
in this directory. `.gitignore` was checked before changes and staging.

1. Baseline exact reproduction used original `8e24b6e` source and installed0.14.0,
   before changes: call `soma.fmri.calibration.calibration_experiment` with
   `{seed:15142,replicates:100,q:0.05,scenarios:[ar1-null],models:[ols,ar1,ar2]}` to
   a fresh ignored output directory. The method also includes a bounded known GLS
   reference; its summary has no spatial BH estimate. The preserved reproduction
   used `reports/milestone141-reproduction`. Reconstruct X/c by calling
   `soma.experiments.fmri_simulation.simulate` through `soma.fmri.calibration.calibration_run` for each seed; saved supplementary arrays/JSON specify exact
   n100/m343/AR(.6)/burn-in500/df96/q.05. These supplementary files have a separate
   receipt, not retroactive membership in the reproduction output manifest.
2. New source uses `configs/fmri-null-audit.yaml`, sealed by
   `configs/milestone141-freeze.json` together with the protocol/setup config.
   Smoke seed1401000 is separate from final1411000. Run:

   ```sh
   export MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/soma-mpl
   export XDG_CACHE_HOME=/private/tmp/soma-cache OPENBLAS_NUM_THREADS=1
   export OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1
   .venv/bin/python experiments/milestone141/run.py
   ```

   Outputs must not exist. The runner performs calibration and **read-only**
   readiness. It expects private runtime/image snapshots in
   `data/derived/milestone141/`. Runtime snapshot records Docker Server:null,
   client version/architecture and independently queried host RAM. Registry
   metadata scripts fetch small public manifest/config JSON only, never layers;
   these optional scripts need network, ordinary CI does not. Inspect runtime
   afresh before actual preprocessing. `source_hash` hashes sorted module-relative
   names+bytes; AnatomyReport hashes sorted repository-relative names+bytes.
   Different algorithms must not be compared as though equal.
3. Freeze policy and evidence **before** the human gate:

   ```sh
   .venv/bin/python experiments/milestone141/seal_and_pilot.py
   ```

   This refuses existing seal/output paths. Preserve any earlier run under a
   separate ignored archive; never overwrite historical reports. The actual
   attempted pilot returned unavailable, zero fits. Late changes corrected
   inherited-event inventory and labels of newly added BY/Bonferroni map outputs;
   final staged experiments/tests were rerun. Earlier M14.1 attempts are preserved
   under ignored archive roots; original M13/M14 artifacts were never changed.
4. Run full pytest (`.venv/bin/pytest -m ''`), ordinary offline pytest, Ruff check,
   Ruff format check, strict mypy on `src/soma`, and pip check. Audit script expects
   full/offline logs at `/private/tmp/soma-m141-{full,offline}-tests.log` and the
   private pre-change file ledger at `data/derived/milestone141/baseline-ledger.json`.
   Then `.venv/bin/python experiments/milestone141/audit.py` validates preserved
   baseline tests/reports, output hashes, raw BOLD hashes, policy/config seals,
   numerical array geometry/finiteness and final code provenance. It exports
   aggregate `verification.json`, including all per-condition uncertainty tables.
   Full raw acquisition checksums remain in existing private source receipts.

Artifacts: diagnostic rows, marginal p arrays, exact designs/covariances,3 PNGs
with underlying NPZ arrays and JSON manifests. All3 plots were visually inspected;
Unicode labels are allowed, object/pickle arrays are rejected. The right-hand
panels reuse left-hand label ordering. Wilson intervals use independent
realizations, not pooled dependent voxels. Mixture FDR uncertainty is a
10,000-replicate percentile bootstrap of128 replicate FDPs (seed1411999), not a
binomial interval; correction/model comparisons share simulations.

No image pull, template download, daemon start, preprocessing execution, human
contrast result or large cohort run occurred. Setup/derivative QC/human retest
acceptance remain explicitly incomplete. No push or Milestone15.
