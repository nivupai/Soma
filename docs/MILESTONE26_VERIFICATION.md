# Milestone 26 verification addendum

Baseline: public sanitized repository, main
`5912057928a305ed0717886cf975512b745f7861`. M25 PR and post-merge workflows each
passed all 13 jobs. Before implementation the preserved 1,487 Python tests passed
(1,470 default + 17 cached integrations); no downloads were used for verification.

## Local gates

- Final fixed-tree full suite: 1,521 passed, 117 warnings, 196.27 s; includes all
  1,487 baseline tests and 34 new physical/numerical/adversarial checks.
- Strict mypy: 280 source files passed. Ruff and formatting passed.
- Frontend: 40 tests passed, TypeScript/ESLint/Prettier/build passed.
- Playwright: 19 passed. Existing tests are unchanged. The actual source-uncertainty
  view was inspected visually; plot-label overlap and marker contrast were fixed.
- All previous nine cross-platform synthetic comparison contracts remain unchanged;
  the new physical tests also run in the existing four-runner/dependency-floor gates.

One earlier full-suite attempt was interrupted after a plotting source file was
edited during a cache-bound test. It contained a failure in that cache-bound test;
the fixed-tree complete repeat passed the original assertion unchanged. No source
or environment integrity guard was relaxed. An initial figure layout failed before
completion; corrected figures were rerendered and inspected. Receipts remain local.

Dependency consistency and vulnerability audits passed in the main environment
and all three fresh noneditable wheel/sdist/source installations. Each passed
core/Explorer smoke checks and all 18 SDK examples; the source checkout also ran
all 18. All 289 installed code/resource files in every environment matched the
reproducible wheel. Disposable installation environments were removed only after
saving receipts/audits; the preserved M24 inference runtime and scientific data
were untouched. The package itself has no PyPI audit record. npm reported zero
vulnerabilities. No known vulnerabilities were found in auditable dependencies.

Two independent fixed-timestamp builds produced identical wheel/sdist bytes.
Every distribution member/payload passed the existing privacy inspection. Final
artifact hashes are in the public verification record (kept outside the sdist to
avoid self-referential build hashes). Gitleaks 8.30.1 and the unchanged privacy
checker found zero material secrets, restricted files or personal home paths.
The existing 65 exact-content reviewed false positives remain unchanged; no rule
or exception was widened. Pattern scanning is not proof of every possible absence.

All 317 protected baseline tests/configurations/experiments remain byte-identical.
The final commit is scanned again before push. Private paths, raw MRI/EEG,
participant derivatives and model weights stay ignored. No real EEG is sent to CI.

## Scientific evidence

`experiments/milestone26/evidence.json` hashes every reviewed synthetic numerical
artifact and figure. The native M17 manifest, M19 seal, physical implementation
hashes, known moments/locations, measured voltages, measurement pairing, per-case
failures, intervals, numerical residuals and resource receipts are preserved.
The design freeze is commit `948d755`, before final outcomes. Distinct generator,
noise, model and method counts are kept separate; no human inference is claimed.
Public SVGs contain synthetic content only. Local PDFs/PNGs are not release inputs.

## Remote gate

M26 must merge only after all scientific, quality, Explorer, security, packaging,
dependency-floor and four-platform comparison gates pass at the intended PR head.
The existing 13-job workflow is preserved. An open PR or local success does not
constitute remote success. Actual PR/run URLs, merge SHA, synchronized main and
post-merge results belong in the final completion receipt and PR record. Repository
visibility must remain PUBLIC. No force push, history rewrite or M27 execution.

## Cross-version typing correction

The first PR run, 43153617215, identified a Python 3.11 / NumPy 2.4.6 overload
error in an unpacked `Generator.uniform` range. Explicit finite float lower/upper
arguments preserve the same frozen 35–65 mm bounds and random stream. Strict
mypy passes against both the local NumPy and NumPy 2.4.6 stubs, with no ignores,
weaker settings or dependency pin used to hide the error. The corrected experiment
was repeated: all truth locations/moments and all scalar values/failure statuses
in the eight case tables are bit-identical. The full source test and fresh-package
gates are repeated on the corrected source. Original public scientific receipts
retain their actual executed implementation hashes, available in commit f91b9f1;
those historical run hashes are not retrospectively replaced by the typing edit.
