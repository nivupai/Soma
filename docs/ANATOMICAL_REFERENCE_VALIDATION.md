# M32 anatomical reference validation

This addendum preserves all M12 reports and results. The frozen M32 protocol is
`experiments/milestone32/design.json` (seal committed before final execution).
IBSR's 18 labeled cases are development/replication data. Five MRBrainS13 labeled
training cases are external methods replication, **not a fresh held-out test set**.
No hidden MRBrainS test labels or headers are opened. Existing multi-Otsu intensity
predictions are generated independently of references; reference masks never become
predictions. No tuning, reference-label resampling or reference-versus-reference scoring.

IBSR ontology: native CSF/GM/WM labels 1/2/3 map to 1/2/3. MRBrainS13 native 1/2 map
to GM=2, 3/4 to WM=3, 5/6 to CSF=1; 7/8 cerebellum/brainstem are excluded only from
scoring. MRBrainS CSF includes falx/sinuses, so it is not a physical conductor-CSF
compartment. Background and excluded classes are explicit in the private confusion
tables; incompatible role or geometry comparisons reject rather than silently align.
Whole-head intensity processing can overassign low intensity extracranial/background
voxels to CSF. This is a baseline failure, not credible complete-head segmentation.

Per-subject/per-class Dice, Jaccard, ASSD, HD95, signed/absolute volume differences,
surface areas and class confusion are retained locally. Public tables contain means
and cohort failure counts only. ASSD and HD95 quantify tissue boundary displacement;
no skull/scalp displacement truth exists. All 23 cases fail the frozen engineering
target (each tissue Dice >= .8 and HD95 <= 5 mm). These are not clinical thresholds.

| Dataset | Cases | Macro Dice | Bootstrap 95% interval | Failed tissue target |
|---|---:|---:|---:|---:|
| IBSR V2 | 18 | .587345 | .576965–.597953 | 18/18 |
| MRBrainS13 training | 5 | .455683 | .361946–.546850 | 5/5 |

Seeded 2,000 subject-resampling bootstrap intervals describe these known cases, not
population generalization. M12 comparison joins every one of 69 tissue rows by private
case identity and label. Largest differences: Dice/Jaccard < 9e-17, ASSD/HD95 < 8e-15 mm,
volume < 1.5e-11 mm³ (CSV roundoff). No historical outcome changes.

| Dataset | Tissue | Dice | Jaccard | ASSD mm | HD95 mm | Signed Δ volume mm³ | Absolute Δ volume mm³ |
|---|---|---:|---:|---:|---:|---:|---:|
| ibsr-v2 | CSF | 0.1113 | 0.0596 | 26.785 | 43.372 | 273709.2 | 273709.2 |
| ibsr-v2 | gray matter | 0.7850 | 0.6476 | 1.097 | 3.296 | -234534.9 | 234534.9 |
| ibsr-v2 | white matter | 0.8658 | 0.7644 | 0.822 | 3.195 | 55360.4 | 63848.8 |
| mrbrains13 | CSF | 0.4782 | 0.3145 | 5.611 | 21.202 | 531876.6 | 531876.6 |
| mrbrains13 | gray matter | 0.5264 | 0.3583 | 7.720 | 32.547 | 599530.6 | 599530.6 |
| mrbrains13 | white matter | 0.3625 | 0.2592 | 11.706 | 38.941 | 168662.6 | 243791.6 |

The provided MNE FreeSurfer aseg labels are automated anatomical support, **not an
independent reference**. No improvement over the historical algorithm or independently
validated skull/scalp/CSF reconstruction is claimed.

Geometry audit: all 36 IBSR image/reference files have coded sforms and absent coded
qforms; native storage is RAS, spacing .837054–1 mm × 1.5 mm × .837054–1 mm. Published
IBSR mm spacing supports the existing explicit units override. All ten MRBrainS
image/reference files have qform code 2/sform code 1, storage LPS and spacing about
.958333 × .958333 × 3 mm. Maximum coded q/s corner disagreement is .429100 mm,
within the frozen .5 mm limit; warnings are retained. Sform selection is explicit.
Two MRBrainS intensities receive the preexisting <=.05 mm identity-world alignment;
no reference labels are resampled. This is convention-aware QC, not fitted registration.

Permission sources: [MNE sample documentation](https://mne.tools/stable/documentation/datasets.html#sample),
[MNE manual sample conditions](https://mne.tools/mne-c-manual/MNE-manual-2.7.3.pdf),
[IBSR release notices](https://www.nitrc.org/frs/shownotes.php?release_id=2316).
Conflicting older notices and the locally supplied MRBrainS Readme/manifest are retained
privately. Source availability does not imply redistribution or clinical/commercial use.
