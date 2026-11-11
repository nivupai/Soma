"""Standalone isolated prediction worker, importing only the selected installed Soma.

Executed by an explicit Python runtime with -I. It never imports a training object
or resolves code from a model artifact. M24's code/environment guards stay intact.
"""

import argparse
from importlib.metadata import version
from pathlib import Path

from soma.core.provenance import sha256
from soma.eeg_benchmark.protocol import MODELS
from soma.external_eeg.models import predict
from soma.human.evidence import read_bundle
from soma.human.permissions import PermissionEvidence, permission_readiness
from soma.model_archive.archive import (
    archive_root,
    inspect_archive,
    numerical_receipt,
    verify_release,
)
from soma.results.io import load_result, read_json


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("request", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    q = read_json(a.request)
    manifest = Path(q["archive"])
    release = inspect_archive(manifest, q["release_id"])
    if version("soma-neuro") != release["software_version"]:
        raise ValueError("Runtime software differs from archived release")
    # No supported learned component can fit inside the inference process.
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from soma.decoding.csp import TrainingCSP
    from soma.decoding.riemannian import CovarianceMDM, TrainingTangentSpace

    def forbidden(*args: object, **kwargs: object) -> None:
        raise ValueError("Fitting is forbidden in the frozen worker")

    for component in [
        Pipeline,
        StandardScaler,
        LogisticRegression,
        LinearDiscriminantAnalysis,
        TrainingCSP,
        CovarianceMDM,
        TrainingTangentSpace,
    ]:
        component.fit = forbidden
    operation = q["operation"]
    if operation == "verify-source":
        if release["dataset"] != "eegmmidb":
            raise ValueError("Source reload requires the authentic human archive")
        permission = PermissionEvidence.from_dict(read_json(Path(q["permission"])))
        result = verify_release(
            manifest,
            q["release_id"],
            archive_root(manifest) / release["probe_file"],
            permission=permission,
            notice=Path(q["notice"]).read_bytes(),
        )
        result.update(scope="SOURCE_RELOAD_ONLY", human_external_trials=0)
        numerical_receipt(result, {}, a.output, "soma.frozen-runtime.verification")
        return
    if operation not in ("predict-synthetic", "predict-external"):
        raise ValueError("Unsupported worker operation")
    packet = Path(q["packet"])
    if sha256(packet) != q["packet_sha256"]:
        raise ValueError("Changed feature packet")
    envelope, numeric = load_result(packet)
    values = envelope["payload"]["values"]
    if envelope["method"] != {"id": "soma.external-features", "version": "1"}:
        raise ValueError("Unsupported feature packet")
    if values["contract"] != release["contract"]:
        raise ValueError("Input reference/channel/units contract is incompatible")
    if operation == "predict-synthetic":
        if (
            release["dataset"] != "synthetic-external-v1"
            or values["dataset"] != "synthetic-target-v25"
        ):
            raise ValueError("Human data cannot enter synthetic execution")
    else:
        if q["release_id"] != "8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85":
            raise ValueError("Unexpected human model release")
        b = read_bundle(Path(q["bundle"]))
        permission = PermissionEvidence.from_dict(read_json(Path(q["permission"])))
        notice = Path(q["notice"]).read_bytes()
        refs = {
            k: (Path(v["root"]), v["relative"]) for k, v in read_json(Path(q["references"])).items()
        }
        if (
            b.document()["dataset"],
            b.document()["version"],
            b.document()["protocol_fingerprint"],
        ) != (values["dataset"], values["version"], values["protocol_fingerprint"]):
            raise ValueError("External evidence/packet binding mismatch")
        for action in ["analyze", "export_aggregate"]:
            if (
                permission_readiness(permission, notice, b, refs, action=action)["status"]
                != "READY"
            ):
                raise ValueError("External prediction permission blocked")
    result = {}
    failures = {}
    for model in MODELS:
        row = release["models"][model]
        try:
            labels, scores, probabilities = predict(
                archive_root(manifest) / row["file"],
                row["id"],
                values["contract"],
                numeric["X"],
                numeric["powers"],
                numeric["covariances"],
            )
            result[model + "_labels"] = labels
            result[model + "_scores"] = scores
            if probabilities is not None:
                result[model + "_probabilities"] = probabilities
        except (ValueError, ArithmeticError) as error:
            failures[model] = type(error).__name__
    numerical_receipt(
        {
            "release_id": q["release_id"],
            "dataset": values["dataset"],
            "protocol_fingerprint": values["protocol_fingerprint"],
            "packet_sha256": q["packet_sha256"],
            "refitted_components": 0,
            "model_failures": failures,
            "software_version": version("soma-neuro"),
        },
        result,
        a.output,
        "soma.frozen-runtime.predictions",
    )


if __name__ == "__main__":
    main()
