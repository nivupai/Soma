# Milestone 22 verification addendum

This addendum records the v0.22.0 work without rewriting prior reports.

| Check | Inspected local result |
|---|---|
| Full cached Python suite | 1,377 passed; all 1,331 original tests plus 46 additions; 117 existing warnings |
| Network-forbidden benchmark suite | 46 passed; sockets denied; fictional inputs only |
| Protected baseline files | 252/252 byte-identical hashes |
| Ruff / format | Pass |
| Strict mypy | Pass, 254 source files |
| Frontend unit tests | 32 passed, including all original 30 |
| Playwright | 15 passed, including all original 14; installed wheel API and configured aggregate |
| TypeScript / ESLint / Prettier / production build | Pass; existing Vite large-chunk advisory remains |
| Python requirements / npm audit | No broken requirements; no known runtime dependency or npm vulnerabilities |
| Fresh wheel / sdist / source | Noneditable core and Explorer smoke checks; all 14 SDK examples in each; pip check passes |
| Installed-environment audit | Zero known vulnerabilities after upgrading vulnerable bootstrap pip 24.0 to a fixed release in all three new environments |
| Two independent fixed-epoch builds | Identical wheel and sdist bytes |
| Native human benchmark | Eleven variants inspected; primary complete; overall PARTIAL preserves sensitivity missingness |
| Gitleaks 8.30.1 / complete privacy gate | Zero material secrets, restricted-data files or personal home paths; same 65 exact reviewed false positives; no expanded exceptions |

The real human execution is local macOS arm64/Python 3.12. GitHub retains the
13-job matrix, including actual macOS arm64/Linux x86_64 Python 3.11/3.12 synthetic
runs. Remote CI is a separate publication gate: inspect the exact feature head,
all 13 PR jobs and four actual synthetic artifacts before merging, then verify
all 13 post-merge jobs, private visibility and local/remote main identity. The
completion report links the observed remote runs; local synthetic results are
not substituted for remote evidence. Synthetic equality does not authorize
human-data cache interchange or independent biological replication.

Ignored local receipts contain detailed logs, installation manifests, private
input/coverage tables, FitAudit memberships, per-trial predictions, native cells
and CI artifacts. Public aggregate hashes and execution/code/protocol identities
are recorded in `experiments/milestone22/evidence.json`. The separate proposal
audit documents two/seven records without published trial-level decisions in the
no-reference/strict-QC sensitivities; their failures and subjects are retained.
No participant signals, rows, pseudonym key, personal paths or new binary
exceptions are published. All six figure types and the Explorer table were
visually inspected; participant forests and screenshots remain ignored.

No new OSF, MRBrainS or audited fMRI evidence was supplied. Those blockers remain
NOT_AVAILABLE; no fMRIPrep or Milestone 23 work was started.
