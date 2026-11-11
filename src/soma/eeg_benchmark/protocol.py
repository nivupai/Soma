"""Fixed scientific design, using M19 seals rather than a new protocol engine."""

import copy
from dataclasses import asdict
from typing import Any

from soma.human.workflow import metadata
from soma.protocol.binding import example_protocol
from soma.protocol.model import Protocol, SealedProtocol, anatomy, closed, methods, seal
from soma.workflow.model import Artifact, Graph, Stage, digest

MODELS = ("dummy", "multiband_lr", "csp_lda", "riemann_mdm", "tangent_lr")
VARIANTS = (
    "primary",
    "narrow_bands",
    "filter_8_30",
    "reference_none",
    "epoch_long",
    "strict_qc",
    "motor_channels",
    "center_only",
    "covariance_lw",
    "runs_8_12",
    "source_30",
)


def design(source_count: int = 35, target_count: int = 30) -> dict[str, Any]:
    return {
        "schema": "soma.eeg.benchmark-design/1.0.0",
        "source_count": source_count,
        "target_count": target_count,
        "cohort_rule": (
            "ascending cached subject numbers; first source_coun"
            "t development; remainder evaluation; no substitutes"
        ),
        "dataset": "eegmmidb",
        "dataset_version": "1.0.0",
        "history": "all cached65 were used in M4/M5; none untouched or external",
        "runs": [4, 8, 12],
        "models": list(MODELS),
        "variants": list(VARIANTS),
        "seed": 22042,
        "preprocessing": {
            "reference": "average",
            "highpass_hz": 1.0,
            "lowpass_hz": 40.0,
            "order": 4,
            "phase": "zero",
        },
        "channels": ["FC3", "FCz", "FC4", "C3", "Cz", "C4", "CP3", "CPz", "CP4"],
        "quality": {
            "channel_ptp_v": 0.0005,
            "trial_ptp_v": 0.0003,
            "excursion_v": 0.00015,
            "flat_std_v": 5e-8,
        },
        "epoch": [1.0, 3.0],
        "context": [0.0, 4.0],
        "fs_hz": 160.0,
        "labels": {"T1": 0, "T2": 1},
        "bands": [[8.0, 13.0], [13.0, 30.0]],
        "minimum_per_class_per_run": 2,
        "search": {
            "logistic_C": [0.1, 1.0],
            "csp_components": [2, 4],
            "csp_regularization": [0.1, 0.3],
        },
        "fixed": {
            "logistic_C": 1.0,
            "csp_components": 4,
            "csp_regularization": 0.1,
            "covariance_estimator": "oas",
            "covariance_relative_floor": 1e-6,
            "covariance_trace_normalize": False,
        },
        "inner_subject_folds": 3,
        "bootstrap_resamples": 1999,
        "confidence": 0.95,
        "null_repetitions": 19,
        "null_models": ["multiband_lr", "tangent_lr"],
        "exchangeability_attested": False,
        "adaptation_models": ["multiband_lr", "tangent_lr"],
        "adaptation_counts": [0, 4, 8],
        "adaptation_run": 4,
        "adaptation_test_runs": [8, 12],
        "interpretation": (
            "exploratory descriptive; no confirmatory/clinical/independent external replication"
        ),
        "uncertainty": (
            "paired target-subject percentile bootstrap conditi"
            "onal on fitted source models; not trial resampling"
        ),
        "missing_policy": (
            "retain all scheduled subjects, records and model cells; never outcome-based exclusion"
        ),
    }


def validate_design(value: dict[str, Any]) -> None:
    expected = design(value.get("source_count", 35), value.get("target_count", 30))
    closed(value, set(expected))
    if (
        value != expected
        or type(value["source_count"]) is not int
        or type(value["target_count"]) is not int
    ):
        raise ValueError(
            "Unsupported or changed benchmark design; use an explicit new protocol amendment"
        )
    if (
        not 3 <= value["source_count"] <= 35
        or not 2 <= value["target_count"] <= 65 - value["source_count"]
    ):
        raise ValueError("Explicit bounded source/evaluation cohorts required")


def configuration(value: dict[str, Any], variant: str) -> dict[str, Any]:
    validate_design(value)
    if variant not in value["variants"]:
        raise ValueError("Unplanned sensitivity")
    p = copy.deepcopy(value)
    if variant == "narrow_bands":
        p["bands"] = [[10.0, 12.0], [15.0, 25.0]]
    elif variant == "filter_8_30":
        p["preprocessing"]["highpass_hz"] = 8.0
        p["preprocessing"]["lowpass_hz"] = 30.0
    elif variant == "reference_none":
        p["preprocessing"]["reference"] = "none"
    elif variant == "epoch_long":
        p["epoch"] = [1.0, 4.0]
    elif variant == "strict_qc":
        p["quality"]["trial_ptp_v"] = 0.00015
        p["quality"]["excursion_v"] = 0.0001
    elif variant == "motor_channels":
        p["channels"] = ["C3", "Cz", "C4"]
        p["search"]["csp_components"] = [2]
        p["fixed"]["csp_components"] = 2
    elif variant == "covariance_lw":
        p["fixed"]["covariance_estimator"] = "ledoit_wolf"
    elif variant == "runs_8_12":
        pass
    p["evaluation_runs"] = [8, 12] if variant == "runs_8_12" else [4, 8, 12]
    p["source_limit"] = (
        min(30, value["source_count"]) if variant == "source_30" else value["source_count"]
    )
    p["normalization"] = "center_only" if variant == "center_only" else "standardize"
    p["variant"] = variant
    return p


def benchmark_protocol(value: dict[str, Any], inventory_fingerprint: str) -> SealedProtocol:
    validate_design(value)
    d = example_protocol("eeg").document()
    meta = metadata("eegmmidb")
    meta["units"] = {"balanced_accuracy": "1"}
    graph = Graph(
        "eeg-benchmark",
        (
            Artifact("request", "benchmark.request", meta, fingerprint=inventory_fingerprint),
            Artifact("summary", "benchmark.summary", meta, producer="evaluate"),
        ),
        (
            Stage(
                "evaluate",
                "benchmark.eeg.evaluate",
                {"request": "request"},
                {"summary": "summary"},
                {"design_fingerprint": digest(value)},
                algorithm_version="22.1",
            ),
        ),
    )
    req: dict[str, Any] = {"stages": {}, "artifacts": {}}
    for a in graph.artifacts:
        v = asdict(a)
        v.pop("id")
        req["artifacts"][a.id] = v
    for s in graph.stages:
        v = asdict(s)
        v.pop("id")
        v["requirement_id"] = "method-" + s.id
        req["stages"][s.id] = v
    d.update(
        id="eeg-benchmark-v22",
        name="Historically reused EEGBCI decoding benchmark",
        version="1.0.0",
        requirements=req,
    )
    sci = d["scientific"]
    sci.update(
        question=(
            "How do fixed Soma decoders generalize across "
            "runs and historically reused EEGBCI subjects?"
        ),
        objective="Leakage-safe held-out fitting evaluation; not new external replication",
        estimand=(
            "equal-evaluation-subject mean balanced accuracy, averaging prespecified eligible runs"
        ),
        population={
            "unit": "subject",
            "dataset_namespace": "eegmmidb-1.0.0",
            "scope": inventory_fingerprint,
            "inclusion": [
                value["cohort_rule"],
                "all three imagery runs available, min two retained trials/class/run",
            ],
            "exclusion": ["prespecified metadata/QC only; failures and missingness retained"],
        },
        conditions=["left hand imagery", "right hand imagery"],
        preprocessing={"evaluate": {"design_fingerprint": digest(value)}},
        analysis_methods=methods(req),
        primary_outcomes=list(MODELS),
        anatomical_conventions=anatomy(req),
        inference={
            "mode": "descriptive",
            "confirmatory_claim_allowed": False,
            "correction": "none",
            "assumptions": [
                (
                    "conditional subject bootstrap; historically reused c"
                    "ohort; exchangeability not independently established"
                )
            ],
        },
        qc={
            "required_stages": ["evaluate"],
            "missing_policy": "retain_all_units_and_report",
            "exclusion_policy": "prespecified_non_outcome_only",
        },
        sensitivity_analyses=list(VARIANTS[1:]),
        limitations=[value["history"], value["interpretation"], value["uncertainty"]],
    )
    d["optional_metadata"] = {
        "eeg_benchmark": value,
        "inventory_fingerprint": inventory_fingerprint,
    }
    d["replay_policy"]["synthetic_only"] = False
    return seal(Protocol.from_dict(d))


def inspect_protocol(sealed: SealedProtocol) -> dict[str, Any]:
    p = sealed.protocol.document()
    v = p["optional_metadata"]["eeg_benchmark"]
    validate_design(v)
    expected = benchmark_protocol(v, p["optional_metadata"]["inventory_fingerprint"])
    if expected.protocol.fingerprint != sealed.protocol.fingerprint:
        raise ValueError("Changed benchmark protocol identity or scientific fields")
    return dict(v)
