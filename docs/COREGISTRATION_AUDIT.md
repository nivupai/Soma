# Coregistration audit

The [frozen reliability protocol](MODEL_RELIABILITY_PROTOCOL.md) follows inspection
of the original M8 arrays and code. No old artifact was rewritten. Both original
coregistration and uncertainty commands were rerun unchanged before new numerical
algorithms; the historical metrics reproduced exactly.

## What the residuals establish

Sample's distributed transform is explicitly HEAD→FreeSurfer MRI surface RAS,
with metre-valued translations. Cardinal digitization is HEAD LPA/nasion/RPA;
78 EXTRA points are measured headshape, 61 digitized EEG points include the
reference, and 4 HPI points are distinct. The 59 retained EEG channels agree
exactly with their measured digitization identities. The adapter verifies curated
sample identity, source subject IDs, boundary IDs 1/3/4 and MRI coordinate frame.
MRI surface RAS is distinct from scanner RAS; MGH voxel maps are recorded.

MRI fiducials are estimated from fsaverage through the participant Talairach
transform, not independently picked anatomical landmarks. The distributed
transform's discrepancies to those proxies are 23.508/10.030/27.357 mm. There is
no evidence that the supplied transform was fitted to these exact estimated
targets. This mismatch of reference definitions can produce a large discrepancy
without a transform-direction or unit error; its anatomical cause cannot be
identified without independent MRI landmarks. It is not measured registration
error. See [MNE's documented fiducial and transform definitions](https://mne.tools/stable/generated/mne.coreg.Coregistration.html).

Equal-weight Soma SVD and MNE's supported fiducial fit agree to about 8e-16 in
matrix entries. Their proxy fitting residuals are 7.202/7.478/9.344 mm, but their
common-scalp headshape RMS is 11.561 mm, worse than the distributed transform's
4.651 mm. Optimizing those three proxy residuals does not establish anatomy.
Soma's trimmed nearest-ico3-vertex ICP yields 4.598-mm exact triangle RMS.
MNE's headshape-only ICP yields 3.653 mm on that same evaluation scalp, starting
from its fiducial fit and optimizing its high-resolution loaded scalp. Different
initializations, scalp geometry, trimming and correspondence objectives preserve
valid numerical differences; neither reference transform is anatomical truth.
No fitted alternative replaces the historical transform.

The report separates fitting residual, headshape→triangle distance, differences
from the supplied transform and unavailable real true-transform error. Raw
fiducials, headshape, EEG positions, transformed points, scalp and matrices are
saved in `audited-geometry.npz`. The supported MNE procedure uses 30 ICP iterations,
headshape weight 1, EEG/HPI/fiducial weights 0 and no scaling. See
[MNE automated coregistration](https://mne.tools/stable/auto_tutorials/forward/25_automated_coreg.html)
and [coordinate conventions](https://mne.tools/stable/auto_tutorials/forward/20_source_alignment.html).

## Independent asymmetric phantom

A distorted ellipsoid has a known 3D rigid transform, four fitting landmarks and
eight held-out targets. Seed 42, 100 trials per scenario; independent Gaussian,
correlated and anisotropic landmark models, outliers, wrong correspondences,
headshape noise, partial coverage and 60-degree initialization error are separate.
Noise is generated in the declared physical frames. Rotation/translation errors,
training RMS, held-out TRE and empirical 6×6 transform-error covariance are saved.
Covariance parameter order is relative MRI rotation vector (radians), then MRI
translation difference (metres); cross terms have their corresponding mixed units.

The first held-out target's nominal 95% delta-method ellipsoid covers 92/100,
98/100 and 94/100 trials under independent/correlated/anisotropic Gaussian models.
Wilson 95% coverage intervals are [0.850,0.959], [0.930,0.994], [0.875,0.972].
These are finite simulation checks under assigned distributions, not calibrated
participant anatomical uncertainty. Correlated noise reduces mean fitting RMS
to 1.509 mm while held-out TRE is 2.807 mm. Independent noise gives 2.353-mm fit
and 2.331-mm TRE. A low training residual need not predict independent accuracy.

Full headshape noise gives 0.547-mm mean held-out TRE; partial coverage 0.899 mm.
Incorrect initialization leaves about 54.9-degree rotation error and 44.4-mm TRE.
Wrong full-rank correspondences are rejected in all 100 negative-control trials.
Outlier robust fitting is explicitly separate, with mean TRE 2.926 mm versus
7.043 mm for the ordinary contaminated fit. None of these synthetic outcomes
certifies the participant's anatomical registration.
