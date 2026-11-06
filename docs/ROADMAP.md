# Roadmap

Milestone 1 supplies dataset selection, validated arrays, spectral estimation,
synthetic benchmarks and reproducible descriptive outputs. Scientific limitations
include no artifact handling, no reference model, no event-based segmentation,
no uncertainty estimates, and no inferential interpretation of band differences.

Milestone 2 should focus on EEG preprocessing and event-based analysis:

1. Define reference and bad-channel policies with explicit Raw copies, provenance,
   filter transition bands, padding, phase and edge behavior.
2. Add run-aware rest/left/right epochs with annotation durations, rejection rules,
   baseline windows, boundary handling and trial counts.
3. Validate anti-aliasing before resampling; document filter impulse/frequency
   responses and power effects using synthetic artifacts and known transients.
4. Estimate event-related mu/beta changes within trials, retain subject hierarchy,
   quantify uncertainty, and prevent temporal leakage in any decoding evaluation.
5. Expand cached real-data fixtures and data-quality reports before multicohort work.

Later milestones may add classical motor-imagery decoding with leakage-safe
cross-validation, time-frequency estimation with explicit temporal/frequency
tradeoffs, and oscillation/aperiodic separation with model diagnostics.

Source localization needs measured/digitized sensor positions, reference-aware
forward models, conductivity assumptions, coregistration, inverse regularization
and simulation-based ground truth. Structural MRI needs explicit image affine,
coordinate-frame and surface topology contracts, validated external tooling and
reproducible anatomical processing. fMRI needs motion/confound handling, design
matrices, autocorrelation models and corrected statistical inference. Multimodal
registration requires explicit transforms, interpolation choices and quantitative
registration checks. These features are deferred; the present directories hold
no pretend numerical implementations.
