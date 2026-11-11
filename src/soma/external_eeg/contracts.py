"""Closed feature and evaluation contracts over the existing M19 seal."""

import copy
from typing import Any

from soma.eeg_benchmark.protocol import MODELS, benchmark_protocol, configuration, design
from soma.protocol.model import Protocol, SealedProtocol, seal
from soma.workflow.model import digest

CHANNELS = ["FC3", "FCz", "FC4", "C3", "Cz", "C4", "CP3", "CPz", "CP4"]
BNCI_CHANNELS = [
    "Fz",
    "FC3",
    "FC1",
    "FCz",
    "FC2",
    "FC4",
    "C5",
    "C3",
    "C1",
    "Cz",
    "C2",
    "C4",
    "C6",
    "CP3",
    "CP1",
    "CPz",
    "CP2",
    "CP4",
    "P1",
    "Pz",
    "P2",
    "POz",
]
MODES = ("EXACT_FROZEN", "HARMONIZED_FROZEN", "EXTERNAL_REFIT")


def parameters() -> dict[str, Any]:
    return configuration(design(), "primary")


def feature_contract(reference_scope: str = "bnci-average-22") -> dict[str, Any]:
    return {
        "channels": CHANNELS.copy(),
        "fs_hz": 160.0,
        "epoch_s": [1.0, 3.0],
        "units": "V",
        "bands": [[8.0, 13.0], [13.0, 30.0]],
        "filter": {"highpass_hz": 1.0, "lowpass_hz": 40.0, "order": 4, "phase": "zero"},
        "reference_scope": reference_scope,
        "event_origin": "imagery-cue",
        "labels": {"left_hand": 0, "right_hand": 1},
        "feature_order": "channel-major-band-minor",
        "covariance": "oas-relative-floor-1e-6-no-trace-normalization",
    }


def validate_contract(c: dict[str, Any]) -> None:
    if c != feature_contract(c.get("reference_scope", "")) or c["reference_scope"] not in (
        "bnci-average-22",
        "eegbci-average-all-eeg",
        "synthetic-nine",
    ):
        raise ValueError("Unsupported feature contract or label inversion")


def compatibility(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    validate_contract(source)
    validate_contract(target)
    differences = [k for k in source if source[k] != target[k]]
    return {
        "status": "COMPATIBLE" if not differences else "NOT_COMPARABLE",
        "differences": differences,
        "exact": not differences,
        "missing_channel_interpolation_allowed": False,
    }


def plan(mode: str = "EXTERNAL_REFIT", split: str = "subject") -> dict[str, Any]:
    if mode not in MODES or split not in ("subject", "session"):
        raise ValueError("Explicit supported mode/split required")
    return {
        "schema": "soma.external-eeg.plan/1",
        "dataset": "bnci2014-001",
        "version": "upstream-001-2014-unversioned",
        "mode": mode,
        "split": split,
        "subjects": list(range(1, 10)),
        "sessions": ["T", "E"],
        "runs": list(range(1, 7)),
        "source_subjects": list(range(1, 6)) if split == "subject" else list(range(1, 10)),
        "target_subjects": list(range(6, 10)) if split == "subject" else list(range(1, 10)),
        "source_sessions": ["T", "E"] if split == "subject" else ["T"],
        "target_sessions": ["T", "E"] if split == "subject" else ["E"],
        "source_contract": feature_contract("eegbci-average-all-eeg"),
        "target_contract": feature_contract(),
        "class_mapping": {"1": 0, "2": 1},
        "exclude_classes": [3, 4],
        "artifact_policy": "reject_source_flags",
        "quality": parameters()["quality"],
        "eligibility": "both sessions, six runs/session, minimum two accepted trials/class/run",
        "models": list(MODELS),
        "parameters": {
            "dummy": {},
            "multiband_lr": {"classifier__C": 1.0},
            "csp_lda": {"csp__n_components": 4, "csp__reg": 0.1},
            "riemann_mdm": {},
            "tangent_lr": {"classifier__C": 0.1},
        },
        "harmonization": {
            "resample": [16, 25],
            "cue_offset_s": 2.0,
            "reference": "average-all-22-before-channel-selection",
            "units_conversion": "uV-to-V",
            "epoch_trial_start_s": [3.0, 5.0],
            "resample_event_rounding": "nearest-sample",
        },
        "seed": 23042,
        "bootstrap_resamples": 1999,
        "selection": "fixed-M22-no-search",
        "inference": "descriptive-subject-bootstrap-conditional-on-source; no human p-values",
        "sensitivities": [],
        "adaptation": "NOT_IMPLEMENTED; no implicit target calibration",
        "missing_policy": "retain every planned target; no outcome exclusion",
        "download_authorized": False,
        "original_m22_model_available": False,
    }


def validate_plan(p: dict[str, Any]) -> None:
    if p != plan(p.get("mode", ""), p.get("split", "")):
        raise ValueError("Changed scientific protocol; explicit new amendment required")


def seal_plan(p: dict[str, Any], inventory: str, models: dict[str, str]) -> SealedProtocol:
    validate_plan(p)
    d = copy.deepcopy(benchmark_protocol(design(), inventory).protocol.document())
    d.update(id="external-eeg-v23", name="External EEG transfer readiness", version="1.0.0")
    d["scientific"].update(
        question="Can fixed Soma decoders transfer to previously unused EEG?",
        objective="Separate exact, harmonized and external-refitted evaluation",
        estimand="equal target subject/session/run balanced accuracy",
        inference={
            "mode": "descriptive",
            "confirmatory_claim_allowed": False,
            "correction": "none",
            "assumptions": ["participant resampling; limited small-N precision"],
        },
        limitations=[
            "No original M22 fitted models preserved; no independent replication by filename"
        ],
    )
    stage = d["requirements"]["stages"]["evaluate"]
    stage["implementation"] = "external.eeg.evaluate"
    stage["algorithm_version"] = "23.1"
    stage["parameters"] = {"plan_fingerprint": digest(p), "model_ids": models}
    for artifact in d["requirements"]["artifacts"].values():
        artifact["metadata"]["dataset_identity"] = p["dataset"]
        artifact["metadata"]["estimand"] = "equal target participant/session/run balanced accuracy"
        artifact["metadata"]["limitations"] = [
            "Original M22 fitted state unavailable; no biological certification"
        ]
    from soma.protocol.model import anatomy, methods

    d["scientific"].update(
        population={
            "unit": "subject",
            "dataset_namespace": p["dataset"],
            "scope": inventory,
            "inclusion": ["declared subject/session roles; all six task runs with both classes"],
            "exclusion": [
                "source artifact flags and prespecified physical QC only; no replacements"
            ],
        },
        conditions=["left hand imagery", "right hand imagery"],
        preprocessing={"evaluate": copy.deepcopy(stage["parameters"])},
        analysis_methods=methods(d["requirements"]),
        anatomical_conventions=anatomy(d["requirements"]),
        primary_outcomes=["balanced_accuracy"],
        sensitivity_analyses=[],
    )
    d["optional_metadata"] = {
        "external_eeg": p,
        "inventory_fingerprint": inventory,
        "model_ids": models,
    }
    return seal(Protocol.from_dict(d))


def inspect_plan(s: SealedProtocol) -> dict[str, Any]:
    d = s.protocol.document()
    m = d["optional_metadata"]
    p = m["external_eeg"]
    validate_plan(p)
    if (
        seal_plan(p, m["inventory_fingerprint"], m["model_ids"]).protocol.fingerprint
        != s.protocol.fingerprint
    ):
        raise ValueError("Changed sealed protocol identity")
    return dict(p)


def candidate_audit() -> dict[str, Any]:
    return {
        "schema": "soma.external-eeg.audit/1",
        "status": "BLOCKED",
        "source_dataset": "eegmmidb-1.0.0",
        "target_dataset": "bnci2014-001",
        "candidate_version": "NEMAR-v1.0.3; upstream unversioned distribution is distinct",
        "expected_subjects": 9,
        "expected_sessions": 18,
        "expected_binary_trials_before_qc": 2592,
        "observed_subjects": 0,
        "observed_sessions": 0,
        "observed_trials": 0,
        "license": "CC-BY-ND-4.0",
        "permission_status": "LOCAL_ANALYSIS_SUPPORTED_BY_NOTICE; AGGREGATE_EXPORT_UNRESOLVED",
        "local_data": "NOT_AVAILABLE",
        "acquisition_authorized": False,
        "historical_exposure": (
            "No matching tracked Soma source/config/history found; not proof of global independence"
        ),
        "model_compatibility": {
            "status": "BLOCKED",
            "original_m22_model_available": False,
            "missing_fitted_state": [
                "classifier coefficients/intercepts",
                "scaler scales",
                "MDM class means",
            ],
            "required_channels_present_in_documented_montage": True,
            "differences": [
                "250 versus160 Hz",
                "22 versus all64 EEG average reference",
                "cue2s after trial start",
                "acquisition hardware filters",
            ],
        },
        "modes": {
            "EXACT_FROZEN": "BLOCKED",
            "HARMONIZED_FROZEN": "BLOCKED",
            "EXTERNAL_REFIT": "BLOCKED",
        },
        "performance": [],
        "domain_shift": {
            "status": "METADATA_ONLY",
            "source_channels": 64,
            "target_channels": 22,
            "source_hz": 160,
            "target_hz": 250,
            "amplitude_and_covariance": "NOT_RUN",
        },
        "alternative": {
            "dataset": "Cho2017-GigaDB-100295",
            "license": "CC0-1.0 in primary DataCite record",
            "catalog_conflict": (
                "MOABB catalog lists CC-BY-4.0; primary record must be checked per distribution"
            ),
            "status": "CANDIDATE_ONLY; no local files/acquisition authorization",
        },
        "warnings": [
            "No human external predictions or accuracy estimates exist",
            "Local seals are not external preregistration",
            "No consent inferred from accessibility",
            (
                "Metadata pages contain third-party benchmark context; "
                "no Soma target outcomes inspected"
            ),
        ],
        "confirmatory_claim_allowed": False,
        "independent_external_replication": False,
    }
