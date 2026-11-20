# Inputs for M33; no M33 experiment executed

`experiments/milestone32/M33-inputs.json` is the machine-readable handoff. The baseline
is one QC-only MRI-derived three-compartment model, not validated anatomy. Private
receipts retain actual surfaces, transforms, source coordinates, quadrature, reference
roles and forward fields. A recipient must independently obtain authorized source data.
Public aggregates and protocol/code hashes permit audit without image linkage hashes.

Measured inputs: reference tissue ASSD/HD95 and volume differences for 23 known cases;
MRI voxel spacing; electrode/scalp fit discrepancy; 64/128 candidate discretization;
MNE mesh refinement 14.56% (coarse target FAIL) and 5.12%; matched BEM difference 6.81%.
Tissue errors are dataset/ontology-specific and cannot become skull/scalp error priors.
One conductor anatomy cannot estimate between-person conductor variability.

Proposed **exploratory sensitivity families**, not empirically calibrated probability
laws: normal surface displacement ±.5/1 mm (voxel-scale probes); rigid translations
1/3 mm and rotations 1 degree; skull conductivity factors .5/1/2 around .006 S/m;
64/128 source candidates and finer mesh levels. No confidence or credibility coverage
is established by these values. Electrode fit is not TRE. Skull/scalp/CSF ground truth,
independent registration truth and conductivity measurements are missing. M33 must
freeze its own protocol and justify broader ranges before inspecting its outcomes.

The source domain is the actual eligible GM voxel measure, conservatively contained
in the inscribed inner-skull region, not the spherical M31 quadrature. Only 72,414 of
552,800 provided GM voxels (13.10%) are covered; full-cortex conclusions are unsupported.
No perturbation factorial or uncertainty propagation is executed in M32.
