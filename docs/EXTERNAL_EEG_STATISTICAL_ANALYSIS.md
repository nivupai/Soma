# External EEG uncertainty and methodological challenge audit

Use the participant as the sampling unit. Average run/session balanced accuracy
within participant, then weight participants equally. Report planned/complete/missing
counts, mean/median and pointwise95% subject percentile intervals (1999 resamples,
seed23042), conditional on fitted source models. Subject-disjoint refitting has
four planned test participants; cross-session evaluation has nine, with the same
participants represented in training. These are different estimands.

Small-N empirical intervals have limited precision and no guaranteed nominal
biological coverage. They omit random source-population refitting uncertainty.
No human p-value or superiority decision is produced. Confusion counts, recalls
and probability scores are explicitly pooled trial summaries; they are not
independent participant sample sizes. MDM margins are not calibrated probabilities.
Raw predictions and participant scores remain private; native aggregates disclose
missingness. Blocked evaluation has no performance or uncertainty estimate.

## Separate methodological challenge audit

This is a separate audit by the implementation agent, not independent human peer
review or blinded external validation. Numerical parity uses independently invoked
existing estimators; that does not resolve biological or legal objections.

| Challenge | Finding / unresolved objection |
|---|---|
| Label inversion | Official class order and run context checked; adversarial inversion rejected |
| Frozen fidelity | OPEN: original M22 coefficients/scales/class means were not preserved |
| Dataset choice | Based on requested candidate, montage/task/session/rights; no Soma outcome search |
| Prior exposure | No matching tracked history; public catalog benchmark context was present during metadata retrieval |
| Target leakage | Training-only fitted state; subject/session disjointness and perturbation tests |
| Session identity | T/E actual sessions; wrong filename/session pairing rejected; runs are not sessions |
| Feature changes |22-channel reference,250→160Hz resampling and cue remapping explicitly differ |
| Small-N inference | OPEN: four subject-transfer targets or nine known-participant session targets |
| License/redistribution | OPEN: ND aggregate sharing needs separate review; no signals acquired or published |
| Exclusions | Fixed artifact/physical QC; missing planned targets retained; actual human coverage zero |
| Overstated validation | BLOCKED is not replication; no model reconstructed and no human scores fabricated |
| Adapter validity | Fictional MAT/reference tests pass; real BNCI files have not validated the adapter empirically |

An authorized future acquisition or source-only reconstruction must not backdate
this protocol or call a new source fit the original archived M22 model. A new
explicit plan and a review of these objections are required before interpretation.
