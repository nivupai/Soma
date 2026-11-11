"""Read-only candidate metadata; never downloads signals or accepts access terms."""

from typing import Any

from soma.external_eeg.contracts import CHANNELS
from soma.model_archive.archive import inspect_archive


def acquisition_plan() -> dict[str, Any]:
    return {
        "schema": "soma.external-acquisition/1",
        "status": "EXTERNAL_DATA_ACQUISITION_BLOCKED",
        "signal_downloads": 0,
        "authorization": "NOT_GIVEN",
        "local_permitted_root": "data/external",
        "approval_needed": [
            "explicit dataset/distribution and acquisition authorization",
            "review source license and aggregate-export conditions",
            "current content-bound M20/M21 evidence for actual analysis",
            "review exact file manifest and hashes before execution",
        ],
        "consent_verified": False,
        "selection": "task compatibility and rights evidence; no external accuracy selection",
        "candidates": [
            {
                "dataset": "bnci2014-001",
                "version": "unversioned upstream MAT; hash snapshot required",
                "mirror": "NEMAR nm000139 v1.0.3 (distinct distribution)",
                "url": "https://bnci-horizon-2020.eu/database/data-sets",
                "license": "CC-BY-ND-4.0",
                "subjects": 9,
                "sessions_per_subject": 2,
                "expected_files": 18,
                "download_bytes": None,
                "size_status": "upstream size not verified; mirror size is not upstream size",
                "checksum_procedure": (
                    "record HTTPS source URL, byte length and SHA256 for all18 original "
                    "MAT files; verify structure/session/event/channel metadata"
                ),
                "raw_available": "public linked MAT; not acquired",
                "channels": 22,
                "fs_hz": 250,
                "required_mapping": {"1-left_hand": 0, "2-right_hand": 1},
                "excluded_classes": [3, 4],
                "compatibility": (
                    "all9 nominal ROI names; 22-channel average reference differs from source64"
                ),
                "differences": [
                    "250 to160Hz resampling",
                    "microvolts to volts",
                    "trial-start3–5s equals cue-relative1–3s",
                    "reference and hardware filters differ",
                ],
                "restrictions": (
                    "ND: private adapted analysis and sharing are distinct; "
                    "aggregate-export review unresolved"
                ),
                "permission_review": (
                    "local-analysis notice support only; no acquisition approval or "
                    "external M21 bundle"
                ),
            },
            {
                "dataset": "cho2017",
                "version": "GigaDB DOI10.5524/100295; hash snapshot required",
                "url": "https://gigadb.org/dataset/100295",
                "rights_evidence": "https://api.datacite.org/dois/10.5524/100295",
                "license": (
                    "CC0-1.0 in primary DataCite; MOABB catalog CC-BY-4.0 discrepancy retained"
                ),
                "subjects": 52,
                "sessions_per_subject": 1,
                "expected_files": 52,
                "download_bytes": None,
                "size_status": "NOT_VERIFIED",
                "checksum_procedure": (
                    "verify exact GigaDB file manifest/checksums and selected "
                    "distribution before approval; snapshot SHA256 and lengths"
                ),
                "raw_available": "public original repository; not acquired",
                "channels": 64,
                "fs_hz": 512,
                "required_mapping": (
                    "left/right imagery labels and cue origin require exact-distribution validation"
                ),
                "compatibility": (
                    "full nine-channel spelling/order/reference must be verified; no "
                    "inferred exact transfer"
                ),
                "differences": [
                    "512 to160Hz",
                    "reference/cue timing and original units require verification",
                    "one session cannot reproduce two-session design",
                ],
                "restrictions": (
                    "rights notice does not establish participant consent or Soma "
                    "execution authorization"
                ),
                "permission_review": "NOT_REVIEWED; no acquisition authorization",
            },
            {
                "dataset": "bnci2014-004",
                "version": "unversioned upstream MAT; hash snapshot required",
                "url": "https://bnci-horizon-2020.eu/database/data-sets",
                "license": "CC-BY-ND-4.0",
                "subjects": 9,
                "sessions_per_subject": 5,
                "expected_files": 18,
                "download_bytes": None,
                "size_status": "NOT_VERIFIED",
                "checksum_procedure": (
                    "verify18 subject T/E MAT containers, five nested sessions, "
                    "checksums, actual montage/events"
                ),
                "raw_available": "public linked MAT; not acquired",
                "channels": 3,
                "fs_hz": 250,
                "required_mapping": "binary left/right imagery; verify original MAT labels",
                "compatibility": (
                    "INCOMPATIBLE: only C3/Cz/C4; six required channels absent; "
                    "interpolation forbidden"
                ),
                "differences": ["bipolar reference", "250Hz", "feedback and five sessions"],
                "restrictions": "ND aggregate-export review unresolved",
                "permission_review": "NOT_REVIEWED; no acquisition authorization",
            },
        ],
    }


def verify_transfer(path: Any, identity: str, candidate: str) -> dict[str, Any]:
    release = inspect_archive(path, identity)
    matches = [c for c in acquisition_plan()["candidates"] if c["dataset"] == candidate]
    if len(matches) != 1:
        raise ValueError("Unsupported external dataset identity")
    c = matches[0]
    return {
        "schema": "soma.model-transfer/1",
        "release_id": identity,
        "dataset": candidate,
        "authentic_new_state_verified": True,
        "original_m22": False,
        "exact_transfer": "NOT_COMPARABLE",
        "harmonized_transfer": "INCOMPATIBLE"
        if c["channels"] < len(CHANNELS)
        else "REQUIRES_NEW_SEALED_HARMONIZATION_AND_REVIEW",
        "external_refit": "SEPARATE_EXPERIMENT_NOT_EXECUTED",
        "contract": release["contract"],
        "metadata_differences": c["differences"],
        "permission_status": c["permission_review"],
        "human_evaluation": "BLOCKED",
        "human_subjects": 0,
        "performance": None,
        "no_inference_executed": True,
    }
