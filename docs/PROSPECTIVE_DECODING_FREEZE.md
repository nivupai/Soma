# Prospective decoding freeze

Frozen at **2026-11-07T05:29:04.732664+00:00** before any access to real subjects 36–65.
The implementation was committed as `3816e4e`. Validation passed 312 tests, all
256 baseline files unchanged, Ruff/format/mypy/dependency and CLI checks.

Frozen checksum: `7eced826d6024e633400917fb9dc1c2db26898b85b9ef6b6da47e67603f5d439`.
Initial protocol: `11912588d1457a334580eab3fa1093367a762ee94c0157ed6d71cdaa849547bf`.
Source digest: `8b737ed92e21614a9b013671`.

All four final development modes completed, including 19 nested null refits.
Model parameters below were selected solely by prespecified development-only
grouped inner CV, with equal-subject balanced accuracy and first-entry ties.
All nine models will be reported; no held-out winner will be selected.

```json
{
  "motor_mu_lr": {
    "classifier__C": 1.0
  },
  "motor_bands_lda": {},
  "multiband_lr": {
    "classifier__C": 1.0
  },
  "burst_lr": {
    "classifier__C": 0.1
  },
  "csp_lda": {
    "csp__n_components": 4,
    "csp__reg": 0.1
  },
  "covariance_lda": {},
  "euclidean_mdm": {},
  "riemann_mdm": {},
  "tangent_lr": {
    "classifier__C": 0.1
  }
}
```

Primary preprocessing remains average-reference 1–40 Hz with the fixed nine
channels and common [1,3) analysis/[0,4) context. The post-hoc development
preprocessing diagnostic does not change this. Test participants cannot enter
scalers, burst thresholds, CSP, tangent references, class means or tuning.

The explicit next command is:

```bash
soma decode evaluate-heldout --subjects 36:65 --config configs/decoding-frozen.yaml --output reports/m5-heldout --fetch
```

The command rechecks development data and code before creating an access-start
receipt and fetching/reading held-out EDFs. Zero-shot, fixed labeled adaptation
and within-held-out-subject fitting are separately labeled modes. Repeating the
same fixed evaluation is a reproduction, not another prospective cohort. This
is a locally timestamped and committed methodological study, not an externally
registered clinical trial or random population sample.
