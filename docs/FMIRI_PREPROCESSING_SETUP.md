# Milestone 14.1 fMRI preprocessing readiness

Read-only audit of the existing ds000114 subset; no additional participant MRI,
image layers or templates downloaded. The untouched subset passes the locally
installed official BIDS validator (wrapper3.0.2). Raw dataset BIDSVersion remains
1.0.0rc2; warnings remain, including unknown old version, recommended metadata and
events-column documentation. PASS is input consistency evidence, not preprocessing
or anatomical registration certification. The validator receipt preserves actual
wrapper/schema metadata; do not confuse its schema fields with the raw version.

The existing selected participant has test/retest motor-execution BOLD and T1w
references: two of each. Both BOLDs have184 volumes, TR2.5s. The dataset-level
`task-fingerfootlips_events.tsv` is inherited across sessions; subject-filtered
queries initially omitted it. Milestone14.1 corrects that inventory query with a
regression check. No raw file or metadata was changed. Acquisition metadata
includes SliceTiming, EchoTime, TR and FlipAngle; PhaseEncodingDirection is
absent. No field maps, existing derivatives, transforms or confounds were found.
No susceptibility-distortion-correction claim is supportable from these inputs.
The private inventory saves exact paths, header geometry, metadata and BOLD
hashes; prior ignored acquisition receipts preserve downloaded source hashes.

## Actual environment and blockers

Docker client29.9.2 runs on Darwin/arm64; `docker version` reports Server:null.
No daemon startup attempted. Apptainer, Singularity and fmriprep executables are
absent from PATH. Host RAM16GiB; approximately34.7GiB disk was free at audit.
Docker VM RAM/architecture and amd64 emulation performance are unverified.

Pinned image: `nipreps/fmriprep:25.2.7`, public registry manifest digest
`sha256:bd222fba3a9f07d6ecaa680c412907945106b846a76cd4fbfd86e61667c435f8`.
Public config reports linux/amd64 and2,651,482,191 compressed layer bytes. Only
registry metadata was fetched. Local image presence could not be verified without
a daemon; the receipt's false availability flag means **not verified locally**.
No layer pull occurred. ARM host requires explicitly verified amd64 execution.

FreeSurfer license is absent from inspected configured/common locations.
`--fs-no-reconall` disables surface reconstruction, not all possible FreeSurfer
license requirements. Required TemplateFlow/anatomical assets (OASIS30ANTs,
MNI152NLin2009cAsym and MNI152NLin6Asym) are absent or unverified. Directory counts
alone would not prove a complete cache. Provision resources and verify every
required cached file before any offline launch. No license contents are recorded.

## Exact plan, deliberately not executed

`reports/milestone141-preprocessing-plan/command.sh` is the exact shell-quoted
machine-local command; `bids-filter.json` selects only the existing motor task and
two sessions. `configs/fmri-preprocessing-plan.yaml` fixes resources and outputs.
To regenerate the plan use `experiments/milestone141/run.py` (see experiment
README); readiness only creates a plan, never invokes Docker or downloads assets.

Equivalent command, run from the repository root **only after resolving blockers**:

```sh
docker run --rm --pull=never --network=none --platform linux/amd64 \
  --memory 12000m --cpus 4 \
  -v "$PWD/data/external/ds000114:/data:ro" \
  -v "$PWD/derivatives/ds000114-fmriprep-25.2.7:/out" \
  -v "$PWD/data/derived/ds000114-fmriprep-work:/work" \
  -v "$HOME/.cache/templateflow:/templates:ro" \
  -v "$HOME/.licenses/freesurfer/license.txt:/opt/license.txt:ro" \
  -v "$PWD/reports/milestone141-preprocessing-plan/bids-filter.json:/config/bids-filter.json:ro" \
  -e TEMPLATEFLOW_HOME=/templates \
  nipreps/fmriprep@sha256:bd222fba3a9f07d6ecaa680c412907945106b846a76cd4fbfd86e61667c435f8 \
  /data /out participant --participant-label 01 \
  --bids-filter-file /config/bids-filter.json \
  --output-spaces T1w MNI152NLin2009cAsym:res-2 \
  --subject-anatomical-reference unbiased \
  --fs-no-reconall --fs-license-file /opt/license.txt \
  --nthreads 4 --omp-nthreads 1 --mem-mb 12000 --notrack -w /work
```

Provision/verify the exact image digest, runtime and template/license files;
pre-create output/work directories. Confirm adequate VM resources and disk for
uncompressed image, intermediates and outputs (compressed image size is not a
space estimate). Resolve/record the missing-SDC strategy without fabricating
PhaseEncodingDirection. This offline command has no pull or validation bypass and
will fail if assets are unavailable. The external image's embedded validator may
also differ from the installed input validator; record its actual outcome.
Raw mounts are read-only, outputs/work separate and ignored. The offline template
mount requires a complete locally readable cache; unexpected missing resources
must fail explicitly. HTML review, transforms and geometry QC are mandatory
before fitting any human model. No anatomical accuracy is inferred from names.

The command flags were checked against the [25.2.7 tagged parser](https://github.com/nipreps/fmriprep/blob/25.2.7/fmriprep/cli/parser.py)
and [versioned usage documentation](https://fmriprep.org/en/25.2.7/usage.html).
In this release the obsolete bare `--longitudinal` flag is replaced by
`--subject-anatomical-reference unbiased`. This builds a joint within-participant
anatomical reference across visits and is suitable for a descriptive longitudinal
pilot; it is not an independent held-out visit preprocessing protocol. No claim
of full container execution validation is made while the daemon is unavailable.
The validator receipt records wrapper package3.0.2/schema field1.11.2 and an
embedded summary schemaVersion2.0.1 separately. It reports111 warning entries
(seven code classes) and no errors; warnings are preserved rather than suppressed.
