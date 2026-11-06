# Roadmap

Milestones 1 and 2 provide explicit dataset ingestion, validated signal arrays,
NeuroDSP spectra, reproducible synthetic laboratories, continuous preprocessing,
template electrode geometry, duration-aware events, logged extraction/QC, valid
rest references and sensor-level Morlet/ERD descriptions. They include no MRI,
source localization, ICA, neural networks, decoding or cross-validation pipeline.

A future Milestone 3 could focus on preprocessing sensitivity, uncertainty and
multi-run EEG replication, subject to a separate request:

1. Quantify how reference choice, filter settings, QC thresholds and rest strategy
   affect per-run conclusions; inspect flagged data before adopting automation.
2. Compare runs 4/8/12 with explicit selection, trial counts and hierarchical
   subject/run structure; do not pool trials into population claims.
3. Add bootstrap/permutation procedures only with defined estimands, exchangeability
   assumptions, multiplicity handling and simulation-based coverage checks.
4. Evaluate artifact assessment against manually reviewed examples; consider
   documented optional ICA only after channel geometry/QC/reference validation.
5. Add time-frequency uncertainty and oscillatory/aperiodic diagnostics if the
   scientific questions and numerical validation justify the extra models.

Later classical decoding would require leakage-safe evaluation. Source
localization needs measured/digitized sensor positions, reference-aware forward
models, conductivity assumptions, coregistration, regularization and simulations.
Structural MRI needs image-affine/frame and topology contracts; fMRI needs motion
and confound handling, design matrices and autocorrelation-aware inference.
Multimodal registration requires explicit transforms and quantitative checks.
These remain deferred and are not represented by pretend implementations.
