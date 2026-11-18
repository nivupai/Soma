# Discrepancy attribution and unresolved evidence — M28

No sign, coordinate, conductivity-label, geometry-remeshing, sensor-projection or
reference-matrix mismatch was found in the audited adapters. The declared physical
problem and effective canonical meshes match. This rules out those tested contract
errors, not every possible implementation defect.

The strongest supported explanation is a finite-resolution interaction between
layered resistive interfaces and the different collocation/IP versus symmetric
formulations. The gap occurs in concentric layered geometry too, so nonsphericity
is not required. Both solvers improve against the exact homogeneous reference;
in layered spherical controls, the collocation difference from the semi-analytical
reference remains larger and decreases more slowly. Nonspherical inter-solver
error falls markedly at the finest mesh but remains above target. These controlled
observations identify numerical discretization/formulation as a contributor;
they do not uniquely separate every kernel, IP term or limiting bias.

| Prespecified treatment, head0 / heldout head5 | Quantitative evidence |
| --- | --- |
| Increased OpenMEEG integration, order5/adaptive1 | Field change .0036% / .0033%; gap norm ratio 1.00008 / 1.00009. This tested integration treatment cannot explain the large observed gap. |
| MNE isolated-problem correction disabled | MNE field change 90.7% / 89.6%; paired gap norm increases 2.462 / 2.442 times. Disabling stabilization worsens agreement; it is not a correction selected for acceptance. |
| Inner / middle / outer interface refined alone | Gap norm ratios about 1.18 / .93 / .88, consistent across both heads; mixed discretization interactions remain. |
| Skull conductivity doubled to .008 S/m | Relative differences become 21.414% / 21.096%, while absolute gap norm ratios are .987 / .980. This changes the physical problem and does not rescue the original .004 S/m comparison. |
| Original cap and four deep locations | Exactly recovers 17.610% / 16.912%; all six original results are preserved. Changing source/sensor sampling changes the aggregate, not the validity of the historical result. |

At the finest mesh, the diagnostic OM→MNE scalar is .9007–.9038 and the residual
after scalar alignment is 4.91–5.27%. Thus magnitude and spatial pattern both
contribute. Signed pattern correlations for off-grid XYZ columns span .993974–
.999699; high correlation does not establish voltage agreement. No scalar is
applied to acceptance or inverse fields. Off-grid source-wise XYZ differences
span 8.633–20.427%. Mean individual-column relative errors are 11.514% / 11.561% /
11.550% for X/Y/Z, with substantial depth/source variation; no single axis swap
or sign error explains the residual. These are different aggregations, not
interchangeable estimates. Positive/negative arbitrary moments and fixed-reference
sensitivities are retained separately.

The original 16–18% result is not replaced by a fictitious corrected pass. The
full finest primary fields differ by 11.709–12.208%; all six fail the original
10% target. Some deep-source subsets cross that threshold, but subset selection
is not an allowed primary claim. Numerical correctness of code and passing CI
are separate from scientific agreement. Independent four-layer agreement remains
NOT_ESTABLISHED. FEM_NOT_PERFORMED; PHANTOM_NOT_AVAILABLE. Human source accuracy,
anisotropic conductors and real anatomy are unvalidated.

Proposed next falsifiable experiment: independently derive layered-sphere series
and freeze a resource-bounded interface-separation/refinement schedule to test
whether both formulations approach a shared limit. This is a proposal only;
Milestone 29 has not begun.
