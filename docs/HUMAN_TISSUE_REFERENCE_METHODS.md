# Milestone 11 human reference addendum — methods and restrictions

This addendum integrates the actual user-extracted local releases at baseline
10ead8c; it does not rewrite historical experiments that correctly reported missing
data. The new [sealed protocol](MILESTONE11_HUMAN_PROTOCOL.md) and
`configs/human-tissues-freeze.json` precede scoring. The exact executed code and
input inventory were bound again after development and before external evaluation.

## Privacy and access

The existing user-added `/data/external/` exclusion was verified before changes.
No files from that tree are tracked. Participant records, source headers, native
paths/IDs, per-subject CSV/JSON, predictions, validity images, arrays and MRI figures
remain under Git-ignored `reports/` or `data/derived/`. The output guard refuses
participant artifacts elsewhere in the checkout. Committed tests use synthetic
fixtures; public docs/receipts contain aggregate findings and code/protocol identity.
Raw files and earlier reports are never overwritten. No data are downloaded or
published; no remote push is included.

The local MRBrainS Readme describes the 2013 challenge modalities and manual label
ontology. MANIFEST.TXT lists TrainingData.zip, TestData.zip and Readme.txt with
sizes; all sizes match. Extracted training NIfTIs match individual archive members.
This establishes consistency with the supplied distribution, not cryptographic
proof of its original portal provenance. Neither local document grants a data
license or establishes which portal agreement was accepted. Use is the requested
local segmentation-methods research; no commercial/republication permission or
CC license is inferred from the challenge paper's separate article license.
No registration or hidden-label access was attempted.

Citation: Mendrik et al. (2015), doi:10.1155/2015/813696,
https://research.chalmers.se/publication/230909/file/230909_Fulltext.pdf .
IBSR's local notice states Rohlfing's public-domain release and requests citation
to the 2012 image-similarity/tissue-overlap paper. Public release notes retain older
CMA notices as well: https://www.nitrc.org/frs/shownotes.php?release_id=2316 .
MRI redistribution is outside this task regardless of those notices.

## Discovery and geometry

Discovery found 18 IBSR subjects with whole-head T1, supplied stripped T1/brain
mask, anatomical parcellation, non-filled tissue reference and filled derivative.
Uncompressed/duplicate files are inventoried and not counted as extra subjects.
The benchmark selects the compressed stripped T1 and non-filled segTRI reference;
original T1 has a different axis storage/grid and is not naively voxel-matched.

Five MRBrainS training folders contain registered T1, T1-IR, FLAIR, separate 1-mm
T1, eight-class training labels and three-class testing-style training labels.
The 15 test folders are inventoried by file name only. Although label-named files
are present there, their headers/content are not opened or used, and their status
as genuine reference labels is not inferred. The test ZIP is not opened or hashed.

All NIfTI inputs retain both coded forms, axis directions, spacing, units and
source hashes in private receipts. IBSR's singleton fourth axis is explicitly
selected at frame0; genuine time series are refused. Uncoded units are interpreted
as mm using the documented v2 physical spacings and matching headers; source
headers remain unchanged. Only coded sform is used. The original stripped/reference
grids match without resampling.

MRBrainS uses the registered anisotropic T1 and unchanged training-label grid,
not T1_1mm. The Readme establishes the intended alignment. Coded sform is selected
explicitly; qform disagreements are retained, with .5-mm maximum-corner rejection.
Image/reference shape must agree and corner mismatch must be <=.05 mm. Small
within-policy differences receive one explicit identity-world linear intensity
resample, with pull affine recorded; labels never move. Background interpolation
uses the existing resampler's constant zero. The .5/.05-mm rules were fixed from
header inspection before scores. No anatomical fit/registration or score-based
choice of affine is performed. Boundary/interpolation effects remain limitations.

## Ontology, prediction and metrics

IBSR tissue IDs are 0 other, 1 CSF, 2 GM, 3 WM. Its filled CSF derivative and
fine parcellation are not interchangeable references. MRBrainS maps native 1/2
to GM, 3/4 to WM, 5/6 to CSF; 7/8 cerebellum/brainstem are excluded explicitly.
Testing-style labels in the TRAINING partition verify this mapping only. Reference
consistency against itself is never called independent segmentation performance.
CSF reference conventions include structures documented in the Readme, including
sinuses/falx; these are reference semantics rather than conductor certification.

The independent algorithm is the existing Soma global multi-Otsu T1 baseline:
foreground >2% maximum, 256-bin histogram, ascending CSF/GM/WM classes. There are
no trained weights, manual thresholds, reference-derived ROIs, class permutations
or external-result tuning. Threshold fitting sees only that subject's intensities.
IBSR's supplied skull stripping/bias correction shares preprocessing lineage;
Soma did not independently validate skull stripping. MRBrainS's full-head T1
introduces extracranial confounds. Dataset/domain differences are retained.

`LabelVolume` and `score` gain additive `valid_mask` support. Valid-mask identity,
grid, binary codes and nonempty domain are checked. Overlap/specificity/volumes
use valid voxels only. Surface faces require two valid in-volume neighboring
voxels for masked scoring; neither void cuts nor cropped FOV faces create
artificial matching surfaces. Native boundaries use area-weighted voxel-face
centers in mm, with pooled area-weighted HD95. Unobserved boundaries are null,
not perfect distance. Unmasked historical behavior is retained.

Per-subject/tissue tables contain Dice, Jaccard, ASSD, HD95, signed/absolute and
relative volume errors, plus surface Dice/precision/recall at 1/2 mm. Means and
2,000-draw bootstrap intervals use subjects as units, with missingness reported.
IBSR and MRBrainS summaries remain separate: different preprocessing, anatomy,
annotation conventions and acquisition prevent causal interpretation of their
mean difference. No inter-rater uncertainty is available. Twenty-three scans
cannot establish broad population, clinical or conductor-model validity.

## APIs and reproduction

`datasets.human_mri` discovers the actual layout and loads checked native volumes;
the existing reference registry identities and loader adapter are reused.
`validation.human_tissues` builds private inventories and evaluates frozen phases.
Output roots must be new. After activating the environment:

```sh
soma mri inventory-human --output reports/human-inventory-new
soma mri benchmark-human-tissues --inventory reports/human-inventory-new/inventory.json --phase development --output reports/human-development-new
soma mri benchmark-human-tissues --inventory reports/human-inventory-new/inventory.json --phase external --output reports/human-external-new
```

`python experiments/milestone11-human/run.py` reproduces the ordered inventory,
development, source/input freeze and external stages with bounded workers and
private logs. Scientific figures/arrays are saved locally, not committed.
