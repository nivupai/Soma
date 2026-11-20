"""Public scalar aggregates; private anatomy disabled by default and loopback-only."""

import hashlib
import ipaddress
import json
import os
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response

from soma.anatomy.public_head_models import read_public_head_models

from .registry import Registry

REPORT_SHA256 = "5d014a063c48c2ddc2eb715d6850ad0b9f4779fe8f6848bdad9cd4538299403f"


def private_view_allowed(request: Request) -> bool:
    if os.environ.get("SOMA_LOCAL_ANATOMY_VIEWER") != "1" or request.client is None:
        return False
    if any(
        h in request.headers
        for h in ["forwarded", "x-forwarded-for", "x-real-ip", "x-forwarded-host"]
    ):
        return False
    try:
        if not ipaddress.ip_address(request.client.host).is_loopback:
            return False
    except ValueError:
        return False
    if request.url.hostname not in ["127.0.0.1", "localhost", "::1"]:
        return False
    origin = request.headers.get("origin")
    if origin:
        url = urlsplit(origin)
        if url.scheme not in ["http", "https"] or url.hostname not in [
            "127.0.0.1",
            "localhost",
            "::1",
        ]:
            return False
    return True


def private_anatomy_path(path: str) -> bool:
    return path.startswith("/api/mri-head-models/local/") or any(
        part.startswith("m32-") for part in path.split("/")
    )


def example() -> dict[str, Any]:
    raw = files("soma.resources").joinpath("mri-head-models-example-v32.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != REPORT_SHA256:
        raise ValueError("Human MRI aggregate fingerprint mismatch")
    return read_public_head_models(raw)


def router(registry: Registry) -> APIRouter:
    routes = APIRouter(prefix="/api")

    @routes.get("/mri-head-models")
    def report(request: Request, response: Response) -> Any:
        value = example()
        value["local_views"] = (
            [
                dict(id=e.id, label=e.label, kind=e.kind)
                for e in registry.entries.values()
                if e.id.startswith("m32-") and e.kind in ["mri", "anatomical-model"]
            ]
            if private_view_allowed(request)
            else []
        )
        response.headers["Cache-Control"] = "no-store"
        return value

    @routes.get("/mri-head-models/local/{identity}")
    def local_geometry(identity: str, request: Request, response: Response) -> Any:
        if not private_view_allowed(request):
            raise HTTPException(
                403, "Private anatomy requires explicit opt-in and a direct loopback client"
            )
        if not identity.startswith("m32-"):
            raise HTTPException(404, "Explicit M32 local allowlist required")
        try:
            entry = registry.get(identity, "anatomical-model")
        except (KeyError, ValueError, OSError) as exc:
            raise HTTPException(404, "No locally authorized anatomical model") from exc
        value = json.loads(registry.path(entry).read_text())
        if (
            set(value)
            != {"schema", "status", "frame", "meshes", "electrodes_m", "redistribution_permitted"}
            or value["schema"] != "soma.local-anatomy-view/1"
            or value["status"] != "QC_ONLY_ANATOMY"
            or value["frame"] != "MRI_surface_RAS_m"
            or value["redistribution_permitted"] is not False
        ):
            raise ValueError("Unsupported local anatomical evidence; no accuracy upgrade")
        if len(value["meshes"]) != 3:
            raise ValueError("Three explicit conductor boundaries required")
        for mesh in value["meshes"]:
            if set(mesh) != {"vertices_m", "faces", "boundary"}:
                raise ValueError("Unsupported private geometry fields")
            v = np.asarray(mesh["vertices_m"])
            f = np.asarray(mesh["faces"])
            if (
                v.ndim != 2
                or v.shape[1] != 3
                or len(v) > 10000
                or not np.isfinite(v).all()
                or np.max(abs(v)) > 2
                or f.ndim != 2
                or f.shape[1] != 3
                or f.dtype.kind not in "iu"
                or np.any(f < 0)
                or np.any(f >= len(v))
            ):
                raise ValueError("Invalid local mesh coordinates/connectivity")
        if [m["boundary"] for m in value["meshes"]] != ["inner_skull", "outer_skull", "scalp"]:
            raise ValueError("Local boundary order mismatch")
        electrode = np.asarray(value["electrodes_m"])
        if (
            electrode.ndim != 2
            or electrode.shape[1] != 3
            or not np.isfinite(electrode).all()
            or len(electrode) > 256
        ):
            raise ValueError("Invalid local electrode geometry")
        response.headers["Cache-Control"] = "no-store"
        return value

    return routes
