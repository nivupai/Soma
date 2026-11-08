# Human tissue-reference validation

`validation.cohort` reuses M10 LabelVolume and physical surfel scoring. Canonical
targets are 1 CSF, 2 GM, 3 WM. Subject identity, native world-space identity,
ontology and affine grid must agree. There is no fitted registration or automatic
resampling. Mismatched grids need a separate justified nearest-neighbor operation.
Keep original labels; mappings produce separate arrays with provenance.

Every local cohort manifest identifies dataset, authorization, subjects, split,
T1 path, reference path, reference annotation evidence, reference ontology, native
space and acquisition metadata. Optional independent predictions need backend
tool/version/model, input contrast and SHA256, native label mapping, transform
history, options, runtime, truth-used=false and failure diagnostics. The backend
adapter rejects missing/unmapped labels, undeclared native reference codes, and
reference-identical paths/checksums. Header-only re-saves with identical mapped
label content are flagged as requiring a separate independence audit, not treated
as successful evidence. This conservative rule can also flag genuinely perfect
predictions; the diagnostic is retained rather than silently counting them.
Source image hashes reused under different subject IDs are rejected. These checks
cannot prove who annotated an image: documentary provenance remains necessary.
The schema example is `configs/tissue-subjects.example.json`; copy/edit to the Git-ignored local
`configs/tissue-subjects.local.json` when authorized files are supplied. The frozen
M11 split remains fixed; a different subject selection requires a new prospective
protocol. The public cohort API also accepts already compatible subject records.

The simple baseline is Soma's global three-class multi-Otsu, foreground >2% maximum,
256 histogram bins and ascending T1 intensities CSF/GM/WM. It does not ingest a
reference mask or fit/tune to holdout scores. IBSR's supplied skull stripping and
bias correction are upstream preprocessing, not Soma algorithms. This baseline
is deliberately limited; extracranial tissue is a known failure on full-head MRI.
FreeSurfer/SynthSeg outputs can be ingested with an explicit justified mapping;
no model weights or software installations are implicit, and Soma claims no
ownership of third-party segmentation algorithms.

MRBrainS13's `ingest_mrbrains13_training` reads only explicitly authorized training
labels with caller-verified native names. Native 1/2 map GM, 3/4 WM, 5/6 CSF;
7 cerebellum and 8 brainstem are returned as an explicit exclusion mask, not
background truth. That mask must accompany subsequent challenge-compatible scoring.
The adapter returns image, mapped volume, exclusion mask and native mapping receipt;
it does not silently submit to/evaluate hidden labels. See the challenge paper:
https://research.chalmers.se/publication/230909/file/230909_Fulltext.pdf .
The generic cohort scorer expects already compatible three-tissue inputs and does
not silently apply the MRBrainS exclusion mask; passing unmapped eight-class labels
is invalid. No MRBrainS or IBSR human scoring was executed without authorized data.

Metrics include Dice, Jaccard, sensitivity/specificity, absolute/relative volume,
area-weighted ASSD, pooled HD95/max Hausdorff, surface Dice and boundary precision/
recall at 1/2 mm. Boundaries use finite exposed voxel-face centers in physical mm,
not exact continuous tissue surfaces. Missing predicted labels score zero, absent
both are separate, undefined distances stay null. Component counts are native
6-connected topology. Cortical parcellation, human tissue labels, extracerebral
conductor interfaces and numerical mesh suitability remain separate evidence.

IBSR_01 is development, IBSR_02/03/04 holdout. Each subject/failure/missing record is
retained. Subject bootstrap uses 2,000 draws; n<2 has no CI. Documented scanner or
protocol groups need >=2 subjects, otherwise unsupported. Inter-rater uncertainty
is unknown; no voxel-level pseudo-population or anatomical-certification claims.
