# Frozen BEM discrepancy investigation — Milestone 28

The active design is `src/soma/resources/bem-discrepancy-v28.json`, sealed with
Soma M19 in `configs/bem-discrepancy-v28.json`. It is committed before new final
reference outcomes. Local sealing is not external preregistration. Original M27
results are immutable: all six 16.088–17.610% differences were reproduced exactly
before altering adapters. Source/API inspection is exploratory, separate from
final frozen comparisons. The 10% engineering target is unchanged.

Use exact canonical meshes, MRI/RAS metres, source-major XYZ moments in A m,
conductivities in S/m, one sensor array and one average-reference projector for
each pair. Fixed-reference sensitivity is separate; scalar alignment is explanatory
and never changes physical acceptance or inverse estimates. Preserve effective
solver geometry and interpolation diagnostics, rather than trusting seeds.

Uniform levels 1/2/3 have 80/320/1280 triangles/interface. A shared set of 32
level-1 vertices remains present at all levels, removing mesh-dependent sensor
projection in primary comparisons. The original interior-triangle sensor control
is retained. Three equal-conductivity interfaces implement the homogeneous
physical limit in MNE, whose public EEG API rejects one-surface BEM; OpenMEEG
also has a one-interface control. An independently derived 128-term solid-harmonic
Neumann sphere series covers central and off-centre dipoles; 64-term differences
bound series truncation numerically. Layered-sphere comparison uses MNE's explicitly
approximate semi-analytical solver. Six M27 nonspherical heads use both independent
formulations at all levels. Source/interface/noise/regularization details, controls,
metrics, acceptance and resource bounds are explicit in the sealed JSON.

Prespecified paired factors at level 2 on exploratory head 0 and heldout head 5:
MNE isolated-problem off; OpenMEEG quadrature order5/adaptive1; one interface at
level3 with others2; original M27 sensor layout; doubled skull conductivity.
No factor is selected because it gives the smallest discrepancy. These controls
can support bounded attribution, not prove identical discrete solutions or a
unique causal decomposition. Independent refinement comparisons use both solvers'
three recorded operators. All failures remain recorded. Budget: 3600 s total,
360 s/call, 7000 unknowns and 2 GiB estimated dense storage.

Inverse consequences use distinct level3 off-grid truth, levels1/2 estimates,
the M27 48-source grid, regularization and noise schedule. Shared OpenMEEG truth
is disclosed; no algorithm is superior solely because its inverse peak is nearer.
Hierarchical summaries resample heads within fixed families, then sources within
head; orientations and repeated computations are not independent participants.
Full four-layer independent verification remains NOT_ESTABLISHED. FEM was not
performed; measured phantom evidence is unavailable. Human modeling is deferred.


## Post-outcome metadata amendment, revision 2

Revision 1 at 61973db is retained verbatim. The original design JSON and all
actual solver packets specify three layers, but the seal's descriptive
source_conductivity field inherited M27's four-layer model and values. This is a
metadata contradiction, not evidence that the executed pair used different
conductors. Stale generic summary-axis names were inherited too.

Revision 2 explicitly corrects those declarations, records outcome inspection as
yes and links the original fingerprint. No geometry, conductivity passed to solvers,
source, sensor, numerical parameter, threshold or inverse policy changes. The
10% target and original design hash remain fixed. The complete experiment,
including heldout head5 and every factor, is repeated after this correction.
Original outcomes and the first seal are preserved; numerical identity is tested
rather than assumed. This amendment is not represented as pre-outcome registration.
Active seal: configs/bem-discrepancy-v28-r2.json.
