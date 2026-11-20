"""Executed, synthetic-only M26 examples; no remote or local execution endpoint."""

import hashlib
import json
from importlib.resources import files
from typing import Any

from fastapi import APIRouter

from soma.source.uncertainty import DESIGN_SHA256, protocol


def example() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("source-uncertainty-example-v26.json").read_bytes()
    value = dict(json.loads(raw))
    if (
        value["schema"] != "soma.source-uncertainty.explorer/1"
        or value["synthetic_only"] is not True
        or value["human_subjects"] != 0
        or value["design_sha256"] != DESIGN_SHA256
        or value["protocol_fingerprint"] != protocol().protocol.fingerprint
    ):
        raise ValueError("Uncertainty example identity changed")
    value["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def router() -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/source-uncertainty")
    def uncertainty() -> Any:
        return example()

    @routes.get("/nonspherical")
    def nonspherical() -> Any:
        return nonspherical_example()

    @routes.get("/bem-discrepancy")
    def bem_discrepancy() -> Any:
        return bem_example()

    @routes.get("/fem-reference")
    def fem_reference() -> Any:
        return fem_example()

    @routes.get("/mesh-grid")
    def mesh_grid() -> Any:
        return mesh_grid_example()

    @routes.get("/inverse-calibration")
    def inverse_calibration() -> Any:
        return inverse_calibration_example()

    return routes


def nonspherical_example() -> dict[str, Any]:
    from soma.source.nonspherical import DESIGN_SHA
    from soma.source.nonspherical import protocol as nonspherical_protocol

    raw = files("soma.resources").joinpath("nonspherical-example-v27.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "54efb45c457d822e8eadfbd2e5050c5e94b6e9baf5d79c9e9611f32cbd0418f4"
    ):
        raise ValueError("Nonspherical example integrity failure")
    value = dict(json.loads(raw))
    if (
        value["schema"] != "soma.nonspherical.explorer/1"
        or value["synthetic_only"] is not True
        or value["human_subjects"] != 0
        or value["design_sha256"] != DESIGN_SHA
    ):
        raise ValueError("Only reviewed synthetic nonspherical examples accepted")
    value["protocol_fingerprint"] = nonspherical_protocol().protocol.fingerprint
    value["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def bem_example() -> dict[str, Any]:
    from soma.source.bem_discrepancy import DESIGN_SHA
    from soma.source.bem_discrepancy import protocol as bem_protocol

    raw = files("soma.resources").joinpath("bem-diagnostic-example-v28.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "ead5413f9603a131cfae1ac462662a7c4665f6224a9778e18a49a053bd2b18dd"
    ):
        raise ValueError("BEM example integrity failure")
    value = dict(json.loads(raw))
    if (
        value.get("schema") != "soma.bem-diagnostic.explorer/1"
        or value.get("synthetic_only") is not True
        or value.get("human_subjects") != 0
        or value.get("design_sha256") != DESIGN_SHA
        or value.get("threshold") != 0.10
        or value.get("protocol_fingerprint") != bem_protocol().protocol.fingerprint
    ):
        raise ValueError("Unapproved scientific identity/threshold")
    value["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def fem_example() -> dict[str, Any]:
    from soma.experiments.fem_reference import protocol as fem_protocol

    raw = files("soma.resources").joinpath("fem-reference-example-v29.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "17d8fa13741c253483c34f2ea5b8de63ac392b4e64d5175ad931e20d903785bb"
    ):
        raise ValueError("FEM reference integrity failure")
    value = dict(json.loads(raw))
    if (
        value.get("schema") != "soma.fem-reference.explorer/1"
        or value.get("synthetic_only") is not True
        or value.get("human_subjects") != 0
        or value.get("threshold") != 0.10
        or value.get("protocol") != fem_protocol().protocol.fingerprint
    ):
        raise ValueError("Unapproved FEM physical evidence")
    value["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def mesh_grid_example() -> dict[str, Any]:
    from soma.source.grid_diagnostics import validate_evidence

    raw = files("soma.resources").joinpath("mesh-grid-example-v30.json").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "0515d239c5c1d0211add0d3a7b28b5a02204589dcf7e76b9d7865fba9cd8c24f"
    ):
        raise ValueError("Mesh/grid resource integrity failure")
    value = dict(json.loads(raw))
    validate_evidence(value)
    value["content_sha256"] = hashlib.sha256(raw).hexdigest()
    return value


def inverse_calibration_example() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("inverse-calibration-example-v31.json").read_bytes()
    from soma.source.prior_calibration import validate_example

    return validate_example(raw)
