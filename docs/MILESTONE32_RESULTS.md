# M32 results — MRI-derived head modeling

M31 merged at `3aff2339a6d8133815eb1cd9a4fb1d8e134587f8`; post-merge run
44694634385 passed all 14 jobs. Its native Gmsh diagnostic still reports scientific
FAIL with release policy satisfied. M32 starts from synchronized main and preserves
that policy and all historical evidence. Version 0.32.0; no M33 study is started.

An actual local human-MRI workflow executes successfully on one curated MNE anatomy.
It uses MRI-derived provided FLASH boundaries and automated FreeSurfer tissues, not
new extraction or independent ground truth. In addition, independent intensity
segmentation is evaluated on 18 IBSR and five MRBrainS training cases. These are 24
anatomies in distinct dataset roles, with independent tissue references for 23 and
**no independent full-conductor reference**. Data access is local methods research;
no participant assets or raw-image-derived fingerprints are redistributed.

Tissue macro Dice .587345/.455683 replicates M12 to CSV roundoff. All 23 fail the
frozen tissue target and remain NOT_READY as complete head conductors. The MNE
example is QC_ONLY; there are zero VALIDATED anatomies. See the separate reference
validation and conductor QC reports for per-tissue results and explicit limitations.

| Numerical comparison | Relative difference | Frozen target | Outcome |
|---|---:|---:|---|
| MNE level 2→3 | 14.5620% | 10% | FAIL |
| MNE level 3→4 | 5.1172% | 10% | PASS |
| Same-surface MNE/OpenMEEG level 3 | 6.8133% | 10% | PASS |

All four forward operators execute with 140 MRI-frame source positions, 59 sensors,
average reference and rank 58. Nonnull condition numbers are 158486/94912/87918 for
MNE levels 2/3/4 and 69743 for OpenMEEG3. Gauge residual is <2.2e-14 V/(A·m).
BEM algebraic residual is not independently exposed by the API and is explicitly
unavailable; it is not inferred from successful execution. Matched numerical differences
are neither a ground-truth solver error nor anatomical accuracy. Three- versus
four-compartment BEM/FEM physics is not compared.

A bounded inverse uses 12 independently placed off-grid synthetic sources in real
MRI geometry, level-4 MNE truth and level-3 inverse (correlated formulation limitation),
64/128 nested candidates, fixed cell-volume priors and 0/.05 µV noise. At 128 candidates,
mean peak error at .05 µV is Tikhonov 15.989 mm, MNE 14.118 mm and dSPM 25.104 mm;
nearest-candidate error is 5.294 mm. Full conditional results retain all 12 settings.
This establishes software integration, not physiological priors or human source accuracy.

The initial execution completed scientific calculations but failed final aggregate
export on an incorrect QC field name. That implementation error was corrected without
changing thresholds; private receipts from that attempt are retained. Final exact-code
replay and resource measurements are recorded in the verification addendum.

Seven public aggregate SVGs show tissue overlap, boundary errors, volume errors,
readiness, numerical comparisons (including FAIL), mesh quality and conditional inverse
error. Tables include confusion aggregates, cohort intervals, baseline replication and
M33 inputs. Public Explorer shows those scalars. Actual MRI/overlay/mesh visualization
requires explicit operator preparation, opt-in and direct loopback access. It is never
bundled as a public brain demonstration. Full 3D interface remains reserved for M34.

Full-head anatomical validation remains **unachieved**: no independent skull/scalp/CSF
boundary truth, no participant conductivity, no independent registration TRE, no true
human source locations, one conductor example and restricted GM coverage. Improved
segmentation and suitable external full-head references are still necessary. M32 does
not relax its scientific criteria or call the coarse refinement failure a pass.

Final exact-code local replay: 218.013 s, parent peak RSS 875.8125 MiB, maximum solver
worker peak 1400.8125 MiB. Worker peaks are individual-process maxima, not summed or
claimed simultaneous total memory. Every scientific metric and all four lead-field
CSV files match the previous complete run exactly. This is local repeatability only.

Evidence-domain guard correction: see `MILESTONE32_EVIDENCE_GUARD_ADDENDUM.md`. A new
exact-code replay at implementation 8c7e6d6 again gives byte-identical operator files
and identical scientific metrics. Runtime 213.190 s, parent peak 795.9531 MiB,
maximum individual worker peak 1406.0781 MiB.
`execution-history.json` preserves both exact-code resource measurements and code hashes.
