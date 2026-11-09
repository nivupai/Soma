# Session and cohort reliability

Human pilot fits require two eligible preprocessing audits, exact condition names,
comparable acquisition timing/HRF/smoothing and explicit effect-scale identity.
The motor contrasts are Finger,Foot,Lips versus implicit baseline, and
Finger-.5Foot-.5Lips. Motor execution is not PhysioNet motor imagery. Each visit
is modeled separately; no fixed-effects combination erases session differences.

Six measured motion columns are primary. Expanded12 motion uses explicit first
zero derivatives; retained metadata-defined CompCor is a separate strategy.
FD>.5mm spikes and supplied binary one-hot nonsteady-state indicators preserve
every acquisition row. Missing measurements/definitions or unsupported units fail,
without inventing physiology or dropping scans. Mean FD>.5mm,>20% high-motion frames,
rank/conditioning failure or residual DOF<20 excludes. Counts, FD distributions,
DVARS availability, design correlation and exclusion reasons are retained.
Spikes alter rank/DOF while leaving AR adjacency on the original grid. These
nuisance models do not certify physiological denoising or statistical calibration.

Retest metrics require same subject/task/contrast/space, different visits, common
grid, compatible ROI ontology and explicit cross-session alignment evidence.
Report mask intersection, map correlation, positive/negative FDR Dice, world-mm
extremum displacement, ROI effects and signed/absolute/symmetric-relative changes,
voxel RMSE, two-session variance and motion-QC differences. Empty/empty Dice and
zero-denominator relative change are undefined. Extrema are threshold-selected
noisy features, not exact functional landmarks or independent registration truth.

regional_reliability reuses Soma ROI/transform safeguards and requires explicit
atlas name/version/hemisphere convention/label mapping. It reports coverage and
partial-volume warnings, handles absent labels and rejects subject/space mistakes.
Native/template applications require a valid existing chain; a volumetric atlas
label cannot by itself localize detailed motor function. ROI standard error is
unavailable without spatial covariance, even when voxel variances are available.
No real motor atlas is downloaded or implicitly applied to raw images.

Cohort reliability uses balanced participant×two-session ROI tables, requiring at
least5 complete participants for the software ICC estimate. ICC(A,1) is two-way
random, absolute agreement, single measurement. It assumes independent subjects
and exchangeable session conditions. Subject bootstrap intervals, undefined draws,
delete-one estimates and paired-change intervals expose sensitivity; negative ICC
is retained. One participant never yields cohort ICC. Five/ten subjects do not
establish a stable population or clinical reliability guarantee.

Within-participant changes, between-participant variation, within-session model
variance and repeatability are distinct summaries. Registration error, physiological
change and estimation noise are not identified separately by these metrics.
Missing/excluded cases stay in pilot/cohort outcomes; no voxel bootstrap substitutes
for participant resampling. Cohort expansion requires an intact successful pilot
and explicit per-subject import specifications, with no automatic downloads.
