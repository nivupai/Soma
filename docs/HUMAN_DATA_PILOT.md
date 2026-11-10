# Bounded human pilot protocol and results

This is exploratory re-analysis of previously inspected cached data. It is not an
independent prospective replication or a new holdout. Inputs are never downloaded
by adapters or modified. Public license metadata may be explicitly refreshed; no
medical dataset transfer occurs. Private manifests, HMAC keys, native records and
scientific summaries stay in ignored local outputs.

Predeclared selection: the first two cached EEGBCI subject directories, run 4 only;
the first two IBSR subject directories, fixed stripped T1/non-filled reference roles;
all five locally provided MRBrainS training cases for metadata inspection; and the
cached ds000114 participant's two fingerfootlips sessions. Selection order defines
this bounded software pilot, not temporal acquisition order. All selected units are
retained. Existing QC exclusions are recorded at the trial/window level, without
turning trials into participants. No parameter is chosen using benchmark outcomes.

Run explicitly with `scripts/human_pilots.py --output reports/milestone20/pilots`.
Use `--refresh-public-license` only to retrieve official license metadata, never raw
data. The output contains four native metadata execution artifacts, plans, permission
receipts, operational aggregate counts and a private pseudonym key. Private output
directories are mode 0700 and key files 0600. Existing destinations are immutable.

Expected evidence-dependent outcomes: A (EEGBCI) runs existing unilateral-imagery
preprocessing and spectral summaries; B (IBSR) runs fixed independent intensity
predictions and per-tissue Dice/Jaccard/ASSD/HD95/volume metrics; C (MRBrainS) remains
blocked unless the intended use is documented; D (ds000114) inventories both sessions
and remains blocked without compatible audited derivatives/transforms. The Readme's
provided MRBrainS training labels do not make this a fresh holdout. Test file names
may be counted, but hidden test headers, payloads and hashes are never read.

IBSR's upstream skull stripping is shared data preparation. An intensity-only
prediction is independent of the scoring labels in this computation, but does not
eliminate annotation/preprocessing bias. Tissue metrics do not validate skull/scalp
conductors, cortical source geometry or clinical performance. No human fMRI GLM,
reliability estimate or confirmatory test is produced by this pilot.
