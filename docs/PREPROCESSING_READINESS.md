# Audited preprocessing readiness

M21 wraps the existing M14 `PreprocessingBundle`, NIfTI geometry, ITK transform,
confound and design-QC implementations. It adds a typed canonical import manifest,
explicit-root/symlink checks, per-asset hashes, private subject mapping verification,
recording/anatomical correspondence, software/version/configuration/environment
provenance and source-bound BIDS validation evidence. It does not run preprocessing,
register images, fit a human GLM or introduce an estimator.

`PreprocessingManifest` schema `soma.preprocessing.manifest/1.0.0` binds the scoped
identity fingerprint to explicit raw/derivative assets, including source BOLD/T1,
output BOLD, masks, inherited acquisition/events, confounds/definitions, dataset
metadata, transforms, QC and optional validation reports. Import roots are supplied
privately; no unrestricted filesystem search is performed. Current import inventory
is bounded to 20,000 entries per explicit root. Files are hashed before and after
successful auditing. Missing sessions/runs are not invented by the wrapper.

The existing audit verifies source linkage, TR/timepoint/units, NIfTI geometry, masks,
explicit spatial reference, T1 sources, transform direction and controlled landmarks.
M21 also binds transform references to the exact anatomy and source recording. An
identity transform or matching file name is not independent anatomical validation.
Unsupported/missing transformations remain blocked/indeterminate. The retained M14
functional-run importer requires an explicit run identifier; absent-run imports cannot
be promoted by inventing a run number. General absent-run preprocessing execution and
independent common-space/task certification remain unsupported.

QC reuses M14's **minimal measured-confound policy**, with explicit nonsteady-state
indicator validation. Translation units are mm and rotation units rad. FD is mm;
only the undefined first FD is replaced by zero. The acquired grid is retained.
The existing thresholds are mean FD >0.5 mm, more than20% frames with FD >0.5 mm,
and residual design DOF <20. These are inherited research policies, not universal
clinical criteria. DVARS and mask-grid coverage are reported without newly invented
acceptance thresholds. Invalid/missing/conflicting definitions and measurements fail.
A missing outlier column does not prove nonsteady-state detection succeeded.

A BIDS PASS claim needs a bound report, validator/version and matching raw-asset
snapshot fingerprint. BIDS validity, SDC method/justification and reviewed QC are
separate from file presence. Software/container/environment fields are provenance
assertions; no independent execution attestation is implied. Scientific adequacy
remains INDETERMINATE even when technical and measured-QC statuses pass. Neither
state authorizes confirmation or proves a suitable fMRI noise model.

## Actual human preprocessing availability

For cached ds000114, both sessions are raw. The raw dataset's derivative location
and the output location explicitly named in `configs/fmri-preprocessing-plan.yaml`
were inspected. Both contain zero preprocessed BOLD candidates. No real fMRIPrep
bundle or human motion/DVARS/transform QC result was produced. Status: NOT_AVAILABLE.
The existing M20 human GLM restriction remains in force even if a future bundle can
be parsed. This milestone does not remove that execution restriction.

## Opt-in external handoff — not executed

The existing plan pins fMRIPrep **25.2.7**, four threads, 12,000 MB and T1w plus
MNI152NLin2009cAsym res-2 outputs. These are planning allocations, not measured
requirements or a guarantee of fit. Review runtime resources, architecture, storage
and task-specific settings before any separately authorized execution. Reserve at
least the inherited 30GiB free-space preflight margin, plus verified image/templates,
outputs and potentially larger working storage. The actual requirement is unknown.

1. Preserve the cached legacy BIDS inputs unchanged. Create a private staged copy
   only when needed, record every metadata repair, and run current official BIDS
   validation on the exact staged snapshot. Do not use parsing as certification.
2. Independently stage/verify the pinned container digest, appropriate CPU runtime,
   FreeSurfer license and TemplateFlow resources. No Docker install, image pull,
   template fetch or pipeline execution is part of normal Soma commands or CI.
3. Freeze participant/session/task filters, anatomical-reference policy, SDC settings,
   slice-timing reference, output spaces, resources and any random-state controls.
   Session labels do not establish chronology or justify a longitudinal T1 template.
4. Run externally only after resource/licensing/permission review. Mount raw inputs
   read-only; keep derivatives/work/QC private. Record the exact command, container
   digest, environment, logs, start/finish state and complete input hashes. Missing
   resources must fail rather than silently trigger unreviewed downloads.
5. Return derivative `dataset_description.json`, source links, BOLD/mask/T1 assets,
   sidecars, directed transforms/reference images, motion/confounds JSON+TSV,
   nonsteady-state/SDC evidence, HTML QC reports and human review decisions. Preserve
   failures and all selected sessions. Build a canonical import manifest and bind it
   to a new reviewed evidence bundle before auditing.

The local gap report lists missing provenance, directed transforms, QC and timing.
There is no fabricated container digest, resource measurement or successful run.
The CLI accepts no arbitrary shell command and never launches this handoff.

Primary sources: [fMRIPrep 25.2.7 outputs](https://fmriprep.org/en/25.2.7/outputs.html),
[installation](https://fmriprep.org/en/25.2.7/installation.html),
[usage](https://fmriprep.org/en/25.2.7/usage.html),
[release fixes](https://fmriprep.org/en/25.2.7/changes.html).
