# Executable SDK examples

Run from the repository root with an installed Soma and the Explorer extra:
`python -m scripts.run_sdk_examples`. Nothing downloads data. Outputs are strict
JSON, deterministic except manifest timestamp/Git context. For each individual
example use `python -m examples.NAME`.

| NAME | Numerical acceptance |
|---|---|
| mri_geometry | RAS+, 2 mm spacing; voxel/world roundtrip within float precision |
| segmentation | analytic sphere truth; independently thresholded noisy radial intensity; 0 < Dice < 1, HD95 > 0 |
| surface_qc | closed tetrahedron; Euler 2, volume=1e-6/6 m³ |
| eeg_analysis | 10 Hz peak, integrated mu=8e-12 V²; half-open burst intervals |
| source_diagnostics | identity toy forward; lambda2=.1; resolution diagonal=1/1.1 |
| fmri_contrast | opposite signed synthetic effects; descriptive inference |
| provenance | strict JSON roundtrip and matching declared semantics |
| explorer | synthetic catalog HTTP200 with local-only API |

The segmentation predictor uses intensity only; reference labels do not enter its
calculation. Example classes are invented geometric labels, not human tissues.
See SDK documentation for units, assumptions and unavailable uncertainty. These
examples validate numerical and software contracts, never human anatomy or clinics.
