# Changelog

## 0.16.0

- Add explicit `soma.sdk` imaging, EEG, source, fMRI, provenance, synthetic and
  optional Explorer interfaces while preserving existing module imports.
- Add identity/grid checks, voltage validation, undeclared-label rejection and
  conservative result metadata compatibility checks. Preserve inference policy.
- Ship the compatible local Explorer gateway and small policy resource in wheels;
  add `soma-explorer`, typed marker and reviewed source distribution selection.
- Add eight synthetic examples, distribution privacy checks and fresh noneditable
  core/Explorer installation verification. Keep scientific dependencies compatible.
- Correct NumPy typing boundaries across Python3.11/3.12 without changing formulas.
- Separate CI quality/science/packaging/Explorer/security jobs with pinned actions
  and read-only permissions. No public release, PyPI upload or deployment.

Historical scientific reports and original release records are preserved.
