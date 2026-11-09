# M14 validation seed separation, before final Monte Carlo outcomes

The original frozen seed14142 and next stream were exercised by numerical unit
checks and a two-replicate-per-scenario development smoke run. Preserve the original
protocol/config as historical development evidence. The final100-realization
validation uses independent seeds15142–15241 under exactly the same frozen
scenarios, estimators, thresholds and design. No favorable calibration result was
used to choose a noise model or cutoff. This amendment changes seed allocation
only, before accessing those validation streams. Both the original and amended
configuration checksums are retained. Human preprocessing/retest remains unavailable.
