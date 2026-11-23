# M33 skull v3.1 results: external test on SynthRAD2025 head-and-neck (inconclusive)

Protocol: `docs/MILESTONE33_SKULL_PROTOCOL_V31.md`, sealed by the owner before any test case was
scored. Aggregates (CC BY-NC 4.0, no case IDs): `experiments/milestone33/skull-v31-aggregate.json`.

**Disclosed deviation:** after sealing and before any test case had been scored, a smoke test on
a development case showed that the report-only MR/CT consistency check crashed on cropped T1s.
That one report is now omitted when the T1 is not on the CT grid. No exclusion rule or score
changed.

## Outcome

**Readiness: `NOT_READY`, because the test is inconclusive: 0 of 156 cases were evaluable.**
This dataset turned out not to be a valid test of the method. It is not evidence about the
inner-skull refinement either way.

| Count | Cases |
|---|---:|
| Requested | 156 |
| Pipeline failures | 19 (SynthSeg found no brain: 15; FreeSurfer watershed failed: 4) |
| Scored | 137 |
| MRI-only QC failures | 87 of 137 |
| Unflagged and QC-passing (primary analysis) | **0** |

Flags fired on: skull defect 136, field-of-view crop 118, MRI QC 87, vertex truncation 34,
metal 1. The watershed-to-SynthSeg volume ratio had median 3.7 (development range 0.9–1.5).
Even counting every scored case, inner-skull error was 12.1 mm, outer skull 6.4 mm and scalp
2.9 mm. This is the MRI-side pipeline breaking down, not boundary error of the kind measured on
development.

## Why

These are radiotherapy head-and-neck MRIs: 3 mm slices, a wide field of view that includes
neck and shoulders, and clinical contrasts. SynthSeg and the FreeSurfer watershed both failed
on most of them. The method was built and validated on 1 mm brain-protocol T1 (SynthRAD2023
brain), and on that data the earlier sealed test held up (v2 held-out: outer skull 1.58 mm,
scalp 1.13 mm). The scope statement therefore has to say that **the method needs 1 mm
brain-protocol T1**.

On the CT side, the skull-defect and crop flags fired in most cases because the head-and-neck
CT field of view and body mask cut through the skull. So the test data could not supply clean
skull truth either.

## What is established, and what is next

- Established under sealed protocols: on unseen 1 mm brain T1 (v2, 120 cases), outer skull and
  scalp meet their bars and thickness is unbiased. The inner skull without refinement is
  2.4 mm (bar 2 mm).
- Development only (not yet a sealed claim): the learned inner-skull refinement brings the inner
  skull to 1.07 mm, HD95 4.2 mm (leave-one-centre-out, 60 cases).
- To turn the refinement into a sealed claim, it needs an unseen **1 mm brain T1 + CT** set.
  The best candidate is CERMEP-IDB-MRXFDG (healthy adults, MPRAGE + CT), which needs the owner to
  sign a licence.
