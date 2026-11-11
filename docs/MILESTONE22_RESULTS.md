# Milestone 22: actual EEG decoding evidence

Soma v0.22.0. These results evaluate **held-out fitting on historically reused EEGBCI**, not an untouched cohort or independent external replication. Existing scientific estimators, numerical assertions, historical reports and tests are preserved. No new medical data were downloaded.

## Frozen protocol and coverage

Local M19 protocol fingerprint: `3592c080235d3c459e5204a5fe37f9a8a83bd0ef1ff128fd0bb05b9a3cb60127`. The seal precedes this execution's target outcomes; it is not independent OSF registration. The private inventory binds 195 EDFs: all 65 cached participants, imagery runs 4/8/12. Source roles are the original 1–35; evaluation roles 36–65. M4 examined initial 1–5 and replication 6–35; M5 developed on 1–35 and evaluated 36–65. Later pilots further reused 1/2. None is now untouched.

Primary: 65/65 subjects, 195/195 recordings; 2675/2925 retained trials, 250 rejected. Source 1441/1575; evaluation 1234/1350. All 30 evaluation subjects contribute all three runs. Nine fixed motor channels, average reference, 1–40 Hz filter and 1–3 s epochs are unchanged from the old primary protocol. QC precedes classification. See the protocol addendum for two documented implementation corrections, separate aborted outputs and the unchanged scientific seal.

## Primary model performance

Equal run weights within each subject, then equal subject weights. Pointwise 95% percentile intervals use 1999 paired subject resamples, conditional on the fitted source models. N=30 evaluation units; correlated trials are not independent subjects.

| Model | Within-subject BA [95% interval] | Zero-shot BA [95% interval] | Within / zero median |
|---|---:|---:|---:|
| Majority reference | 50.00% [50.00, 50.00] | 50.00% [50.00, 50.00] | 50.00% / 50.00% |
| Log band power + LR | 56.11% [52.25, 59.80] | 60.77% [56.89, 65.06] | 57.14% / 58.33% |
| CSP + LDA | 57.04% [53.98, 60.29] | 54.00% [51.35, 56.66] | 57.14% / 52.86% |
| Riemannian MDM | 54.52% [50.92, 58.31] | 50.87% [50.00, 52.30] | 52.38% / 50.00% |
| Tangent space + LR | 55.33% [51.50, 59.09] | 56.58% [52.86, 60.31] | 55.95% / 54.76% |

Within folds hold out one target run and fit the other two. Zero-shot fitting uses only source subjects. Source-only grouped inner CV selects LR C=1, CSP 4 components/reg 0.1 and tangent LR C=0.1. MDM has no search. These modes have different training budgets and estimands. All 455 primary outer model cells completed.

| Zero-shot model | Accuracy | Right recall | Left recall | AUC | Brier | Log loss |
|---|---:|---:|---:|---:|---:|---:|
| Majority reference | 49.79% | 100.00% | 0.00% | 0.5000 | 0.2500 | 0.6932 |
| Log band power + LR | 60.86% | 49.89% | 71.65% | 0.6679 | 0.2371 | 0.6707 |
| CSP + LDA | 53.93% | 45.68% | 62.31% | 0.6096 | 0.2521 | 0.6996 |
| Riemannian MDM | 50.75% | 64.76% | 36.98% | 0.6399 | N/A | N/A |
| Tangent space + LR | 56.43% | 45.91% | 67.25% | 0.6213 | 0.2541 | 0.7203 |

Pooled confusion counts, means/medians, calibration metrics, descriptive tied ranks, ten pointwise paired contrasts per mode and subject-deletion influence are retained in the aggregate receipt/CSV. MDM distance margins permit AUC but no probability-calibration claim. Source-only scaling, CSP and class/tangent references exclude target subjects. Per-trial covariance is a fixed feature definition, not a fitted target-population reference.

## Prespecified sensitivities

| Variant | Eligible source / target | Eligible records | Retained / known proposals | Power LR zero BA | CSP zero BA | MDM zero BA | Tangent zero BA |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary | 35 / 30 | 195/195 | 2675 / 2925 | 60.77% | 54.00% | 50.87% | 56.58% |
| narrow_bands | 35 / 30 | 195/195 | 2675 / 2925 | 59.11% | 54.00% | 50.87% | 56.58% |
| filter_8_30 | 35 / 30 | 195/195 | 2738 / 2925 | 59.77% | 60.75% | 50.95% | 59.91% |
| reference_none | 29 / 24 | 172/195 | 1976 / 2895 | 57.65% | 52.79% | 50.31% | 56.70% |
| epoch_long | 35 / 30 | 195/195 | 2654 / 2925 | 61.13% | 55.02% | 50.56% | 55.76% |
| strict_qc | 28 / 23 | 168/195 | 1962 / 2820 | 59.78% | 58.33% | 51.02% | 54.72% |
| motor_channels | 35 / 30 | 195/195 | 2721 / 2925 | 57.20% | 52.96% | 51.52% | 57.28% |
| center_only | 35 / 30 | 195/195 | 2675 / 2925 | 60.79% | 54.00% | 50.87% | 56.90% |
| covariance_lw | 35 / 30 | 195/195 | 2675 / 2925 | 60.77% | 54.00% | 50.89% | 56.69% |
| runs_8_12 | 35 / 30 | 195/195 | 2675 / 2925 | 62.92% | 54.34% | 50.83% | 58.63% |
| source_30 | 30 / 30 | 195/195 | 2675 / 2925 | 60.31% | 51.20% | 50.63% | 56.63% |

All ten changes were specified before outcomes; the primary is unchanged. No favorable sensitivity is promoted into a primary winner. The 8–30 Hz sensitivity raises CSP from 54.00% to 60.75%, while power falls 60.77% to 59.77%; it changes retained trials as well as filtering. Results do not isolate a classifier improvement. No-reference and strict-QC lose 6 and 7 planned evaluation subjects respectively; those rows remain explicitly missing, with no replacements. Source inclusion changes likewise remain visible.

The native proposal counter covers decoded preprocessing outputs: no-reference lacks published trial decisions for 2 failed records, strict-QC for 7. Its 2895/2820 proposal totals are **known counts, not complete scheduled denominators**. The separate post-execution header/failure audit in `proposal-accounting.json` reports scheduled annotations and reproduces failure reasons without fitting models or changing scores. Some accepted trials from individually eligible runs are also unused when a subject fails the three-run rule. Therefore native `trials_rejected_or_unavailable` is a known-count difference, not a complete per-trial rejection ledger in those sensitivities. This reporting limitation is explicit.

`source_30` fits only the first 30 source-role participants, although QC/inventory still covers 65. `runs_8_12` changes the endpoint to two runs, keeping the other-two-run within-training rule. Anonymous distributions, complete/planned/missing counts and all within sensitivity intervals are machine-readable. Subject-deletion influence changes aggregation only, without refitting; rankings and paired contrasts are descriptive, not adjusted superiority tests.

## Separate supervised adaptation and null diagnostics

Balanced earliest accepted run 4 calibration trials are disjoint from the identical 819 test trials in runs 8/12 at every calibration count. All 30 targets support all counts. Target-supervised adaptation is not zero-shot transfer.

| Model | k=0 BA | k=4 BA | k=8 BA |
|---|---:|---:|---:|
| Log band power + LR | 62.92% | 62.80% | 63.16% |
| Tangent space + LR | 58.63% | 59.14% | 58.92% |

Adaptation effects are small and nonmonotonic; no optimized benefit is claimed. All bootstrap intervals and separate calibration/test memberships are retained.

| Grouped diagnostic | Null mean | Null range | Exceedances | MC exceedance 95% interval |
|---|---:|---:|---:|---:|
| Log band power + LR | 49.77% | 47.31–51.82% | 0/19 | 0.0000–0.1765 |
| Tangent space + LR | 49.75% | 48.27–51.22% | 0/19 | 0.0000–0.1765 |

Each shuffle is within subject/run, preserving counts, with source selection and fitting refit. Both plus-one diagnostic tail fractions are 0.05. **Human p_value remains null**: real temporal exchangeability is not established, and no nominal significance decision follows. The exact binomial interval measures Monte Carlo diagnostic uncertainty, not biological-effect uncertainty. Only 19 draws give coarse 1/20 resolution. Multiple testing correction cannot repair unverified exchangeability.

## Historical comparison

M5 shared the same primary source/target cohorts, runs, windows, channels, filter/reference, QC and five estimators. All 6170 shared zero-shot trial/model predictions match the preserved M5 CSV exactly: 0 unmatched and 0 changed. This is computational reproduction on reused data, not fresh independent evidence. M5 zero-shot means 60.77/54.00/50.87/56.58% are reproduced; its subject t intervals differ from the new conditional percentile intervals.

Within-subject power/CSP/MDM/dummy predictions also match. Tangent changes 120/1234 predictions because the new predeclared source-selected C=0.1 replaces the historical within default C=1; mean 55.33% replaces 55.17%. This is an explained protocol difference, not evidence of a new validated improvement. Adaptation means reproduce the previous prospective table. The 8–30 Hz sensitivity was motivated by M5 exploratory preprocessing findings. M4 measured sensor power contrasts, which are not independent classifier validation. Historical reports remain unchanged.

## Cost, figures, restrictions and gaps

Final execution: wall 578.62 s, CPU459.54 s, process peak RSS939.70 MiB. Primary includes 19 null refits and 180 adaptation cells. Timings exclude aborted attempts, acquisition, packaging and software tests. Matching fixed preprocessing stages share verified caches. Human execution occurred on macOS arm 64/Python 3.12 only; synthetic cross-platform checks do not establish human-data replication.

| Variant | Wall seconds | Cumulative high-water RSS MiB | Failed outer model cells |
|---|---:|---:|---:|
| primary | 132.31 | 750.27 | 0 |
| narrow_bands | 39.69 | 835.06 | 0 |
| filter_8_30 | 67.00 | 835.06 | 0 |
| reference_none | 48.92 | 835.06 | 0 |
| epoch_long | 61.07 | 835.06 | 0 |
| strict_qc | 48.78 | 860.75 | 0 |
| motor_channels | 47.63 | 860.75 | 0 |
| center_only | 32.13 | 860.75 | 0 |
| covariance_lw | 31.85 | 939.70 | 0 |
| runs_8_12 | 28.06 | 939.70 | 0 |
| source_30 | 38.77 | 939.70 | 0 |

Overall native status is **PARTIAL** because sensitivity QC leaves planned subjects missing; the primary is complete. All 11 configurations finished, with no failed outer model cells among eligible subjects. Native cell/variant/execution checksums and all sealed private file hashes were verified locally.

Public evidence: `experiments/milestone22/aggregate/result.json`, 110-row `performance.csv`, `evidence.json`, `proposal-accounting.json` and six aggregate SVG figures. All six PNG figure types and a30-row participant forest are private/ignored; figures were inspected. Public exports contain no raw signals, participant rows, identifiers, pseudonym key or private paths. Native serialization remains restricted to ignored output; only the explicitly reviewed aggregate receipt and SVGs are copied into publication artifacts.

PhysioNet EEGMMIDB 1.0.0 public ODC-By 1.0 notice supports scoped methods research/aggregate export; a license does not verify individual consent or authorize clinical use. [Dataset and notice](https://physionet.org/content/eegmmidb/1.0.0/). No new OSF registration, MRBrainS authorization, ds000114 derivatives or audited task/session correspondence was provided: NOT_AVAILABLE. No fMRIPrep was launched. Decoding does not validate skull/scalp conductors, anatomical localization, causal physiology or clinical usefulness.

## Verification

Full Python suite:1377 passed (1331 original plus46 additions),117 existing dependency/model warnings. Offline benchmark suite:46 passed with sockets forbidden. All252 protected baseline files retain identical hashes. Ruff, formatting, strict mypy254 modules, dependency checks/audits,32 frontend tests, TypeScript/lint and build pass. [The verification addendum](MILESTONE22_VERIFICATION.md) records installed-package, Explorer and security checks and the exact-head remote CI publication gates. No Milestone23 work is started.
