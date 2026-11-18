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
