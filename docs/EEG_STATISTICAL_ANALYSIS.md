# Subject-level EEG uncertainty and null diagnostics

The independent sampling unit is the dataset-scoped participant. Trial counts are
not an inferential sample size. Average each participant's run-level balanced
accuracies, then weight participants equally. Report mean, median, 95% percentile
interval (1,999 resamples, seed22042), complete/planned/missing counts and pooled
confusions. Resampling paired subject differences preserves within-subject method
comparisons. Ten pointwise pairwise contrasts per mode and tied subject ranks are
exploratory; no adjusted superiority or confirmatory hypothesis decision is made.

These intervals are conditional on fitted source models and the fixed sampled
cohort; they omit uncertainty from refitting a random source population and dataset
selection. Cohort historical reuse, modest N and nonrandom availability limit
population generalization. They are not guaranteed calibrated biological confidence
intervals. Ordinary accuracy, sensitivity (right) and specificity (left), AUC,
Brier and log loss are computed per run and averaged by subject. MDM margins permit
ranking/AUC but **not** Brier/log-loss probability calibration. Dummy predicts the
source training majority (class0 on ties), with training class prior probability.

Two fixed exploratory null diagnostics (band-power LR and tangent LR) use 19 seeded
shuffles independently inside each subject/run, preserving class counts. Every
shuffle refits source nested selection and zero-shot fitting. Null hypothesis:
no signal–label association conditional on those groups/counts. Report observed
statistic, null mean/range, exceedances, plus-one tail fraction and exact binomial
Monte Carlo exceedance interval. Nineteen repetitions have coarse 1/20 resolution.

Real instructed imagery trials may have temporal dependence and instruction/order
confounding. Exchangeability is **not established**. Therefore human `p_value` is
null, no nominal significance decision is authorized, and no multiple-testing
adjustment can rescue an invalid p-value. The Monte Carlo interval measures
simulation exceedance uncertainty, not biological-effect uncertainty. Existing
other-modality statistical inference restrictions remain in force.
