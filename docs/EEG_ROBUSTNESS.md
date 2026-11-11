# Prespecified EEG sensitivities

The primary remains fixed. Each sensitivity changes one declared axis, with the
same source-only inner selection policy and target role. All outcomes, including
worse results, are reported; variants are correlated exploratory analyses.

| Variant | Declared change |
|---|---|
| narrow_bands | mu10–12/beta15–25 Hz features |
| filter_8_30 | fixed8–30 Hz signal filter; historical M5-motivated diagnostic |
| reference_none | omit average reference |
| epoch_long | epoch1–4 s |
| strict_qc | trial150 µV peak-to-peak; excursion100 µV |
| motor_channels | C3/Cz/C4; CSP components2 |
| center_only | training centering without standard-deviation scaling, including inner CV |
| covariance_lw | Ledoit–Wolf per-trial covariance instead of OAS |
| runs_8_12 | evaluate runs8/12 only; within training still other two runs |
| source_30 | first30 source-role subjects train; last5 source roles excluded from fitting |

All variants inventory195 recordings and require three valid runs per participant.
`source_30` retains the same cached/QC inventory but changes fitted source count.
QC/window/channel variants may alter retained trials/eligible subjects; report their
coverage explicitly rather than implying identical test observations. Sensitivity
scores cannot select a new primary winner. Descriptive tied ranks and maximum
change after deleting one subject from aggregation assess concentration; the latter
does not refit a model or demonstrate stability to all population shifts.
