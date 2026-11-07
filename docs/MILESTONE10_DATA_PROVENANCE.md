# Reference acquisition and implementation clarifications

The original [protocol](MILESTONE10_PROTOCOL.md) and five YAML files remain sealed.
These facts were established during acquisition/development; no subject, noise
level, label target or primary regularization was selected using scores.

BrainWeb's official selection form resolves the logical filename
`t1_icbm_normal_1mm_pn0_rf0` to display alias `T1 ICBM normal 1mm pn0 rf0`.
Submitting the filename as the alias initially yielded a 20-byte empty gzip.
That response and its receipt remain quarantined under `brainweb/failed-empty-response`;
it was never treated as an image in scoring. The successful download uses the
same prespecified T1/1-mm/noise0/RF0 settings via the official form, records its
selection-page hash and validates decompressed MINC magic. Offline regression
checks reject empty/HTML gzip responses. All ten discrete reference class counts
match the official table exactly, including 902,912 gray and 674,777 white voxels.
MINC voxel axes are z/y/x, not an assumed NIfTI x/y/z order; the actual header
maps to Talairach RAS in millimetres and is converted to metres by the adapter.

The author Mindboggle OSF README and Zenodo 22070005 license both state CC BY 4.0
for the selected cortical release. Other subcortical/raw scanner records have
separate terms and were excluded. Attribution: Klein and Tourville (2012),
DOI 10.3389/fnins.2012.00171, Mindboggle team, and the Nathan Kline Institute
Rockland source project. The source table maps NKI-RS-22-11 to
NKI_Rockland_3466763. Raw assets remain local and are not redistributed in Git.

The release is grouped in a 5.23-GB ZIP. Exact HTTP ranges selected only its
NKI-RS-22 volume container (924,552,504 bytes) and individual nested surface and
classifier entries. Only subject 11 was extracted for this study. The whole
collection was not downloaded; cohort transport bytes and retained subset are
separately recorded. Current reference cache is approximately 983 MiB.
Native and MNI images/labels and the supplied affine were retained separately.

Manual native cortical labels are stored as float32 **integer codes**, with an
uncoded spatial-unit field. The corresponding supplied native T1 and manual+aseg
headers establish the same millimetre grid; the explicit mm override is recorded.
The loader verifies exact integral values before casting, never thresholds
intensity into manual truth. The classifier uses a 256³ conformed grid; native
manual labels use 192×256×256. Their world-header relation is an exact integer
permutation/crop. A single explicit nearest-neighbor pull reindexes it; no fitted
registration or metric-driven alignment occurs. The supplied atlas split lists
subject 11 as test, not train. JTAtlas40's own scan list is retained separately;
these lists do not prove independence of every historical pipeline component.
The manual reference and automatic classifier can share annotation lineage.

Both manual cortical hemispheres were loaded from original ASCII VTK (138,161 /
142,862 vertices). Their labels are preserved. Their independent surface-to-volume
frame chain was not established, so raw coordinates are retained as supplied and
no invented MRI-frame overlay or conductor validation is performed.

Two development fixtures exposed implementation issues. Applying Multi-Otsu
histogram-bin centers directly as continuous thresholds could skip a class for
three isolated intensity values. Applying the **upper edges of the same fitted
bins** now preserves the histogram partition, verified by an independent three-
value regression. This is not threshold tuning against truth: the BrainWeb Dice
remains poor (development 0.60042, corrected 0.60190). The old development outputs
were not overwritten. A supposed intersecting mesh initially formed a valid deep
indentation; moving its vertex beyond the opposite boundary makes a genuine
intersection, which is now checked and rejected by a dedicated regression.
No algorithm is credited with repairing a nonexistent defect.

Official sources: [BrainWeb anatomical model](https://brainweb.bic.mni.mcgill.ca/brainweb/anatomic_normal.html),
[BrainWeb FAQ](https://brainweb.bic.mni.mcgill.ca/brainweb/faq.html),
[Mindboggle author data page](https://mindboggle.info/data.html),
[author release and license](https://zenodo.org/records/22070005).

Final adapter review found that a blanket NIfTI millimetre override could misread
coded metre/micron inputs. Known header units are now honored; only the verified
uncoded manual-label file receives an explicit mm override in the workflow.
Independent metre, micron and uncoded-unit regression tests guard the conversion.
This changes no selected-data scores or frozen settings, because the other selected
NIfTI files already declare mm. The existing generic NIfTI API was not weakened.
