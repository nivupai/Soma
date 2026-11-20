# M33 segmentation results

Protocol: `docs/MILESTONE33_SEGMENTATION_PROTOCOL.md`, sealed by the project owner in
`configs/m33-segmentation-freeze.json` (SHA256 `ff19125c…0b19`) before any scoring. IBSR
(development) was scored first; MRBrainS (held-out) was scored once afterwards. Aggregates:
`experiments/milestone33/segmentation-aggregate.json`. Participant outputs stay local.

## Held-out: MRBrainS13 training, 5 cases

| Method | CSF Dice | GM Dice | WM Dice | CSF HD95 mm | GM HD95 mm | WM HD95 mm |
|---|---:|---:|---:|---:|---:|---:|
| multi-Otsu control (frozen) | 0.478 | 0.526 | 0.363 | 21.20 | 32.55 | 38.94 |
| multi-Otsu inside intracranial mask (ablation) | **0.733** | 0.732 | 0.819 | **2.70** | 4.61 | 4.00 |
| SynthSeg 2.0 robust | 0.683 | **0.743** | **0.822** | 3.92 | **2.04** | **2.06** |

Paired Dice gain, SynthSeg − control (subject bootstrap 95% interval): CSF +0.205
(0.171–0.239), GM +0.216 (0.179–0.249), WM +0.460 (0.216–0.710).

**Decision (protocol rule): adopt SynthSeg.** It beats the control on every tissue for both
mean Dice and mean HD95 on the held-out cases. Descriptive targets: CSF ≥ 0.60 met (0.683);
GM ≥ 0.80 not met (0.743); WM ≥ 0.85 not met (0.822).

## Development: IBSR V2, 18 cases

| Method | CSF Dice | GM Dice | WM Dice | CSF HD95 mm | GM HD95 mm | WM HD95 mm |
|---|---:|---:|---:|---:|---:|---:|
| multi-Otsu control (frozen) | 0.111 | 0.785 | 0.866 | 43.37 | 3.30 | 3.19 |
| multi-Otsu inside intracranial mask | 0.112 | 0.784 | 0.867 | — | — | — |
| SynthSeg 2.0 robust | 0.141 | 0.858 | 0.873 | 44.14 | 2.45 | 1.95 |

The control reproduces the sealed M11 values exactly (0.1113 / 0.7850 / 0.8658).

## What this says

- **The main cause of the bad scores was missing head masking, as suspected.** On full-head
  MRBrainS images, restricting the unchanged multi-Otsu rule to an intracranial mask lifts WM
  Dice from 0.36 to 0.82 and cuts HD95 roughly tenfold. On IBSR, whose images are already
  skull-stripped, masking changes nothing.
- SynthSeg gives the best gray/white boundaries (HD95 about 2 mm). The masked baseline is
  slightly better for CSF on MRBrainS; SynthSeg is still adopted because the frozen rule
  compares against the control, and it wins on GM/WM boundary accuracy, which matters most
  for source modelling.
- **IBSR CSF stays poor for every method** (Dice ≤ 0.14). As stated before scoring, IBSR's
  CSF class does not cover the subarachnoid space, so correct conductor CSF is counted as
  error. This is a reference limitation, not evidence against SynthSeg.
- This changes no head's readiness label. Skull and scalp are workstream B.
- Five held-out cases support only descriptive claims; intervals are wide (WM especially).
