# Statistical methodology — v0.4.0

The independent population sampling unit is the subject. Averaging repeated
runs and trials reduces within-subject variability without increasing population
N. `infer_mean` consumes one effect per independent subject; grouping and
eligibility are checked before that boundary. Missing observations are counted,
then omitted under the frozen observed-data policy. It does not make MNAR ignorable.

## Intervals and failure behavior

Percentile and basic intervals use SciPy's vectorized subject bootstrap.
Studentization uses the analytic sample-mean standard error in each resample,
with at least 100 valid pivots and at most 5% invalid pivots. BCa uses SciPy and
fails explicitly on warnings/nonfinite limits; it cannot promise small-sample
calibration. A t interval assumes independent normal subject contrasts for exact
coverage, or a finite-variance CLT approximation. Empty/N=1 groups, zero variance,
nonfinite standard errors and invalid adjustments produce statuses and missing
limits. Infinities are rejected. NaNs are counted and either omitted or rejected.
No procedure substitutes for another. All results record N requested/effective,
confidence, seed, resampling count/unit, estimand, assumptions and warnings.

The optional sign-flip test assumes independent symmetric subject effects under
the null. It is not a design-based randomized trial test for this observational
EEG dataset. Only C3/C4 mu primary tests form the Holm family of two. The t
interval was selected before new subjects and remains the primary interval.

Median and 20%-trimmed mean are labeled different location targets. Their
agreement with a mean is descriptive robustness evidence, not invariance.
Run- and trial-weighted means describe different observed-data weightings.
Participants with more surviving trials never get greater primary weight.
Leave-one-run-out recalculates the subject's paired-run eligibility; it can remove
that subject if fewer than two runs remain. Subject influence ranks use absolute
change in the equal-subject population mean.

## Generative models

Normal is an exact independent normal-location benchmark: subject SD 0.4,
mean 0.3. The other models generate subject/run/condition/trial log powers.
Subject intercepts are −24+N(0,1), run intercept SD 0.5, individual condition
effect SD 0.4, run effect SD 0.2, and trial noise SD 0.7. Random trial counts
are uniform integers 8–24. A shared component produces within-condition trial
correlation 0.6. Condition effects are added to the left condition, so
intercepts cancel in the paired contrast. Heteroscedasticity scales each subject’s
noise by 1+2 times the absolute individual effect deviation. Heavy tails use finite-variance Student t(3) noise,
scaled by sqrt(3). Inspect `simulations/hierarchical.py` for all explicit arrays.

Contamination adds +3 to 5% of subjects: the observed mixture mean is 0.45,
while the clean structural effect is 0.3. Preprocessing shift adds +0.15 to the
left condition, with the same two targets. MNAR retains subjects with individual
deviation greater than −0.2 and randomly omits 15% of runs; the selected target
is 0.3+0.4 phi(−0.5)/[1−Phi(−0.5)], approximately 0.504. Effective N is recorded.
The remaining scenarios target 0.3. These are stylized models of log-power
contrasts, not validated biophysical EEG or realistic artifact waveforms.

## Calibration interpretation

The main grid uses seven scenarios, N=5,10,20,30,50,100, 2,000 independent datasets
per cell, and 1,999 subject bootstrap resamples per dataset. Five procedures share
the same dataset and bootstrap stream: their coverage errors are correlated.
Nominal coverage is 95%; failures count as noncoverage in the principal summary.
Conditional coverage, failure/warning rates, widths, bias, variance, RMSE and
structural-target comparisons are also saved. Binomial exact 95% intervals and
MCSE quantify finite simulation error. Full-grid selection after observing this
experiment would require separate validation; no universal winning method is
claimed. The small N normal benchmark demonstrates finite empirical support
and downward bootstrap dispersion, not a software cure from BCa.

References: [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
for methods and degeneracy handling; [PhysioNet EEGMMIDB](https://physionet.org/content/eegmmidb/1.0.0/)
for the original dataset and acquisition description. Actual file metadata is
validated rather than assuming that description holds for every record.

For the sample mean under normal sampling, the empirical distribution's variance
uses denominator N rather than N−1, shrinking the bootstrap spread at small N.
A percentile interval also lacks the Student-t tail correction. With only five
observed subjects, neither more bootstrap draws nor BCa can create missing tail
support. Contamination adds the separate problem that a rare mixture component
may never occur in a small sample. Studentized intervals widen to account for
estimated SE but can be numerically unreliable at tiny effective N: a resample
of N=2 has zero variance with probability 1/2, and N=3 with probability 1/9
when all observations are distinct. Those failures are part of the calibration,
not a reason to silently return another procedure.
