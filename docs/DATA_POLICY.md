# Data policy

This page lists every external dataset that Soma's code, configs, scripts and docs
reference. For each one it records where the data comes from, the terms as far as
the repository's own records establish them, whether the data may be
redistributed, and how a user obtains it.

**This is not legal advice, and a license does not grant permission.** Dataset
terms do not establish participant consent, clinical-use rights or export rights
for any particular analysis; see
[research data permissions](RESEARCH_DATA_PERMISSIONS.md) and
[public research policy](PUBLIC_RESEARCH_POLICY.md). Licenses marked
**unverified** were not confirmed against a primary standard license text. Check
the source before relying on them. Soma's own code license is also not yet chosen;
see the README.

## Global rules

- **No raw dataset files are committed.** `.gitignore` excludes `data/raw/*`,
  `data/derived/*`, `data/anatomy/`, `/data/external/`, `/derivatives/`,
  `reports/*` and `*.local.json`/`.yaml`, plus every medical binary format
  (`*.edf`, `*.bdf`, `*.nii`, `*.nii.gz`, `*.dcm`, `*.fif`, `*.mgz`, `*.mgh`,
  `*.gii`) and model weights. Only `data/raw/.gitkeep` and `data/derived/.gitkeep`
  are tracked.
- **Nothing downloads implicitly.** Every fetch is an explicit subcommand or
  `--fetch` flag that selects specific subjects or files. Analysis commands only
  read local caches. `SOMA_DATA_DIR` sets the raw data root.
- **What is committed:** code, configs, synthetic packaged artifacts
  (`src/soma/resources/`), synthetic study outputs (`experiments/milestone26`–`31`),
  synthetic Explorer screenshots (`docs/assets/explorer/`) and, for M32, public
  *aggregate* tables (`experiments/milestone32/`) that contain no participant
  images, coordinates, identifiers or raw-image hashes
  (`experiments/milestone32/data-provenance.json` records
  `participant_assets_redistributed: false`).

## Datasets

"Local-only" means the data lives only in ignored local paths and is never in Git.
No row below is committed to the repository.

| Dataset | Source | License / terms (as recorded) | Redistributable? | How to obtain |
|---|---|---|---|---|
| **PhysioNet EEG Motor Movement/Imagery (EEGBCI, `eegmmidb`) v1.0.0** | <https://physionet.org/content/eegmmidb/1.0.0/> | Open Data Commons Attribution v1.0 (ODC-By 1.0). Cite Schalk 2009 and Schalk et al. 2004 (`src/soma/datasets/registry.py`). | Yes, with attribution under ODC-By | `soma datasets fetch eegmmidb --subjects N --runs R --data-dir data/raw` (MNE `eegbci.load_data`, explicit selection only) |
| **MNE sample** (`mne-sample`, v0.12) | <https://osf.io/download/86qa2?version=6>; terms at <https://mne.tools/stable/documentation/datasets.html#sample> | Educational/tutorial use. No hardware or MRI-system performance evaluation. M32 provenance records "do not redistribute". No SPDX license found in the archive (**unverified** as a formal license). | No | `soma anatomy inspect --dataset mne-sample --fetch` (full archive via MNE's fetcher) |
| **fsaverage template** (MNE OSF root v2 / BEM v4) | MNE `fetch_fsaverage` (OSF-hosted; see `src/soma/source/template.py`) | FreeSurfer-derived template. Terms **unverified**; the repository records no license for it. | Unverified; treat as no | `soma source inspect-template --fetch` |
| **OpenNeuro ds000117** (multimodal faces, current BIDS snapshot) | <https://openneuro.org/datasets/ds000117>; files from `https://s3.amazonaws.com/openneuro.org/ds000117/` | CC0 per the current snapshot's `dataset_description.json`. The historical OpenfMRI license must not be substituted ([details](INDIVIDUAL_SOURCE_VALIDATION.md)). | Yes (CC0), but participant derivatives still follow Soma's privacy policy | `soma anatomy inspect --dataset ds000117 --discover` (metadata), `--subject sub-01` (explicit selected files with a byte budget) |
| **OpenNeuro ds000114** v1.0.2 (test-retest motor/fMRI) | <https://openneuro.org/datasets/ds000114>, DOI 10.18112/openneuro.ds000114.v1.0.2 | CC0 per its `dataset_description.json`. Cite Gorgolewski et al. 2013. | Yes (CC0), but participant derivatives follow the privacy policy | No Soma fetcher. Download selected files yourself into `data/external/ds000114` ([M14 results](MILESTONE14_RESULTS.md)) |
| **SPM auditory (MoAEpilot)** | <https://www.fil.ion.ucl.ac.uk/spm/download/data/MoAEpilot/MoAEpilot.bids.zip>; terms at <https://www.fil.ion.ucl.ac.uk/spm/data/auditory/> | Personal education and evaluation. Other uses require contacting the FIL methods group. This is not the SPM software license. | No | `soma mri experiment real --dataset spm-auditory --fetch` (HTTP byte ranges, anatomical member only) |
| **BrainWeb** (simulated MRI phantom) | <https://brainweb.bic.mni.mcgill.ca/> | Official citation request. No standard SPDX license located; the repository records "no raw redistribution" (**unverified** as a formal license). | No | `soma mri references fetch --dataset brainweb` |
| **Mindboggle-101** (release3, Zenodo 22070005) | <https://mindboggle.info/data.html>; <https://zenodo.org/records/22070005> | CC BY 4.0 for the current author release. Separately licensed subcortical and raw source archives are excluded. | Yes, with attribution, for the CC BY assets only | `soma mri references fetch --dataset mindboggle-101` (one subject retained; NKI cohort archive transport) |
| **SCI Head Model** (Univ. of Utah, Warner et al. 2019) | <https://sci.utah.edu/sci-head-model/> | Public institutional resource. Attribution and NIH P41 GM103545 / R24 GM136986 acknowledgment requested. No SPDX license (**unverified**). | Unverified; treat as no | `python experiments/milestone11/fetch_sci.py`, then `soma mri references inspect --dataset sci-head` (cached under `data/raw/references/sci-head`) |
| **IBSR v2** (CMA manual tissue labels) | <https://www.nitrc.org/projects/ibsr/> | Notices conflict: a local Rohlfing public-domain release notice with requested citation, plus older CMA research/noncommercial restrictions. Registered NITRC access. **Unverified.** | No; no image publishing | Register with NITRC, extract to `data/external/ibsr/` yourself. Soma requires the local release notice. |
| **MRBrainS13** (training subset only) | <https://mrbrains13.isi.uu.nl/>; paper <https://research.chalmers.se/publication/230909/file/230909_Fulltext.pdf> | Registration and portal access conditions. No license in the local documents. No redistribution or commercial right inferred. **Unverified.** | No | Register with the challenge portal and place data locally (authorized-local only; hidden test labels are never read) |
| **BNCI2014-001** (BCI Competition IV 2a) | <https://bnci-horizon-2020.eu/database/data-sets>; mirror NEMAR nm000139 v1.0.3 (a distinct distribution) | CC BY-ND 4.0 per the BNCI distributor and NEMAR ([audit](EXTERNAL_EEG_DATASET_AUDIT.md)) | Verbatim copies only, with attribution. No modified redistribution. | No Soma downloader. Supply a reviewed local bundle ([acquisition plan](EXTERNAL_EEG_ACQUISITION_PLAN.md)) |
| **BNCI2014-004** (BCI Competition IV 2b) | <https://bnci-horizon-2020.eu/database/data-sets> | CC BY-ND 4.0 | Verbatim copies only, with attribution | Not acquired; no downloader |
| **Cho2017** (GigaDB 100295) | <https://doi.org/10.5524/100295> | Primary DataCite rights say CC0-1.0, but the MOABB catalog lists CC BY 4.0. The discrepancy is retained (**unverified**). | Likely, but unverified | Not acquired; no downloader |
| **MNE bundled montages** (`standard_1005`, `colin27_1005`) | Ship inside the installed `mne` package | Covered by MNE's package license. Template coordinates only, not subject measurements. | Not redistributed by Soma; installed with MNE | Automatic with `pip install` |
| **TemplateFlow / MNI152 templates and FreeSurfer license** (fMRIPrep setup) | TemplateFlow; FreeSurfer | Referenced as prerequisites only and never fetched. Terms **unverified** here. A FreeSurfer license file is user-supplied. | Not redistributed | Install yourself ([preprocessing setup](FMIRI_PREPROCESSING_SETUP.md)) |

Some docs mention OpenfMRI history and the OSF registration metadata
(`soma registration`). These are metadata APIs, not datasets.

## Soma Explorer and public demos

Explorer's default demo is fully synthetic: seeded EEG, an MRI phantom, analytic
sources, simulated fMRI, and packaged hash-checked synthetic artifacts. **A public
or hosted Explorer demo must use only synthetic data or data that is clearly
redistributable** (for example EEGBCI under ODC-By, or CC0 OpenNeuro snapshots,
with attribution and after privacy review). It must never use MNE sample, SPM
auditory, BrainWeb, IBSR, MRBrainS, SCI Head, fsaverage or any dataset marked
unverified or "No" above. The local private anatomical showcase
is loopback-only and opt-in, and participant views are never captured into
`docs/`. See [Explorer security](EXPLORER_SECURITY.md).

## Further provenance

[DATASETS.md](DATASETS.md), [M10 data provenance](MILESTONE10_DATA_PROVENANCE.md),
[external head model references](EXTERNAL_HEAD_MODEL_REFERENCES.md),
[human tissue reference methods](HUMAN_TISSUE_REFERENCE_METHODS.md) and
[external EEG authorization](EXTERNAL_EEG_AUTHORIZATION_V25.md).
