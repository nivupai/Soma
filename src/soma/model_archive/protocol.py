"""New source-only M19 protocol with immutable M22-derived method settings."""

from typing import Any

from soma.eeg_benchmark.protocol import benchmark_protocol, design
from soma.external_eeg.contracts import feature_contract, parameters, plan
from soma.protocol.model import Protocol, SealedProtocol, anatomy, methods, seal
from soma.workflow.model import digest


def training_protocol(synthetic: bool = False) -> dict[str, Any]:
    return {
        "schema": "soma.model-training/1",
        "release_name": "soma-eegbci-source-v24" if not synthetic else "fictional-archive-v24",
        "dataset": "eegmmidb" if not synthetic else "synthetic-external-v1",
        "dataset_version": "1.0.0",
        "subjects": list(range(1, 36)) if not synthetic else list(range(1, 10)),
        "runs": [4, 8, 12] if not synthetic else list(range(1, 7)),
        "contract": feature_contract(
            "eegbci-average-all-eeg" if not synthetic else "synthetic-nine"
        ),
        "configuration": parameters(),
        "parameters": plan()["parameters"],
        "dtype": "float64",
        "numerical_features": {
            "log_band_power": "natural log of integrated Welch PSD in V^2",
            "covariance_units": "uV^2; fixed V to uV before trial-local OAS",
            "CSP": "natural log mean squared projection; input V multiplied by1e6",
            "PSD": "160sample Welch window;80sample overlap; M22 implementation",
        },
        "classes": [0, 1],
        "seed": 22042,
        "training": "all eligible declared source trials; no calibration or parameter search",
        "validation": "three fixed GroupKFold subject folds; fixed parameters, no search",
        "bootstrap": {"resamples": 1999, "seed": 24042, "unit": "subject"},
        "score_tolerance": {"rtol": 1e-9, "atol": 1e-9},
        "label_comparison": "exact",
        "decision": "score > 0; majority class1 iff prior > 0.5; MDM argmin distance",
        "historical_m22": False,
        "prospective_scope": "archived before external outcomes; historically reused design",
        "external_evaluation": "BLOCKED",
        "private_weights": True,
    }


def seal_training(inventory: str, synthetic: bool = False) -> SealedProtocol:
    value = training_protocol(synthetic)
    d = benchmark_protocol(design(), inventory).protocol.document()
    req = d["requirements"]
    stage = req["stages"]["evaluate"]
    stage.update(
        implementation="model.archive.train",
        algorithm_version="24.1",
        parameters={"training_fingerprint": digest(value)},
    )
    d.update(
        id="eeg-model-archive-v24", name="New source-only fitted-model archive", version="1.0.0"
    )
    sci = d["scientific"]
    sci.update(
        question="Can new source-only fitted state reproduce predictions without refitting?",
        objective=value["prospective_scope"],
        estimand="source-subject out-of-fold balanced accuracy and reload parity",
        preprocessing={"evaluate": stage["parameters"]},
        analysis_methods=methods(req),
        anatomical_conventions=anatomy(req),
        sensitivity_analyses=[],
    )
    sci["population"].update(
        scope=inventory,
        dataset_namespace=value["dataset"],
        inclusion=["declared source cohort only; all scheduled runs and fixed QC"],
        exclusion=["prespecified metadata/QC; no replacements"],
    )
    d["optional_metadata"] = {"training": value, "inventory_fingerprint": inventory}
    return seal(Protocol.from_dict(d))


def inspect_training(sealed: SealedProtocol) -> dict[str, Any]:
    d = sealed.protocol.document()["optional_metadata"]
    v = d["training"]
    synthetic = v.get("dataset") == "synthetic-external-v1"
    expected = seal_training(d["inventory_fingerprint"], synthetic)
    if (
        v != training_protocol(synthetic)
        or expected.protocol.fingerprint != sealed.protocol.fingerprint
    ):
        raise ValueError("Changed model training protocol or unsupported amendment")
    return dict(v)
