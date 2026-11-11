# Frozen-model transfer feasibility

**Original M22 exact transfer is BLOCKED.** M22 preserved predictions, selected
parameters, fit memberships, scaler means, CSP filters and tangent references,
but discarded returned fitted pipeline objects. It did not archive classifier
coefficients/intercepts, scaler scales or MDM class means. Neither a checksum of
predictions nor a partial fit audit recovers those missing fitted states.
No M22 model was reconstructed or refitted for this milestone.

| Contract axis | M22 | BNCI candidate | Consequence |
|---|---|---|---|
| Required ROI | FC3/FCz/FC4/C3/Cz/C4/CP3/CPz/CP4 | All nine documented | No missing-ROI interpolation needed |
| Reference | Average across EEGBCI EEG channels | Left mastoid; harmonized average22 | Different reference operator; absent source channels cannot be invented |
| Sampling |160Hz |250Hz | Fixed antialiased16/25 resampling is harmonization |
| Epoch |1–3s after cue |Cue2s after trial start | Use3–5s after trial start, not1–3s |
| Units |MNE volts |Original MAT microvolts | Explicit1e-6 conversion; no amplitude-based guessing |
| Features |Channel-major mu/beta logs; OAS geometry |Same definitions after declared processing | Shape agreement alone does not establish physical identity |
| Saved model |Unavailable |No target model | Never silently replace with a newly fitted pipeline |

Exact unchanged-model inference, prespecified technical harmonization and external
source-role refitting have separate mode labels. Human frozen modes currently
return BLOCKED because no authentic original M22 capsule exists. A new fit is
always EXTERNAL_REFIT and cannot claim original M22 provenance.

Numeric model capsules use bounded M17 arrays/JSON, never pickle/joblib execution.
Import checks expected identity, arrays/shapes, positive scales, SPD references,
class ordering, feature contract, code identity and environment. Prediction-only
math is checked against all five unchanged Soma pipelines. Import performs no fit;
no test-population tangent/reference update is permitted. Checksums establish
integrity, not authenticated historical origin. Cross-environment/code migration
is not silently authorized by numerical similarity.

M22 settings remain C=1 for power LR, CSP4/reg0.1, OAS relative floor1e-6 without
trace normalization, tangent LR C=0.1 and classifier random_state22042. The new
bootstrap/fictional generator seed is23042. The original methods and M22 outputs
are preserved; no new classifier or outcome-driven tuning is introduced.
