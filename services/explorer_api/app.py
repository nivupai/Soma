"""Local-only typed scientific gateway. Run from the repository root."""

import csv
import hashlib
import io
import json
import threading
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from soma import __version__
from soma.pipeline.cache import source_hash
from soma.sdk.results import SchemaError, compare_results, load_result

from .jobs import Jobs
from .models import (
    Artifact,
    Catalog,
    CompareRequest,
    Comparison,
    Dataset,
    EEGAnalysis,
    EEGMeta,
    EEGWindow,
    Job,
    JobRequest,
    MeshData,
    QCReport,
    Result,
    Slice,
    SourceSeries,
    State,
    VolumeMeta,
)
from .registry import Registry, read_json, sanitize
from .science import Science

ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


def create_app(registry: Registry | None = None, jobs_root: Path | None = None) -> FastAPI:
    registry = registry or Registry()
    science = Science(registry)
    soma_hash = source_hash()
    adapter_hash = hashlib.sha256(
        b"".join(
            p.name.encode() + p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py"))
        )
    ).hexdigest()
    revisions: dict[str, Any] = {}
    analysis_slots = threading.BoundedSemaphore(2)

    def verify(identity: str) -> None:
        if identity.startswith("demo-"):
            if identity not in {
                "demo-eeg",
                "demo-mri",
                "demo-source",
                "demo-fmri",
                "demo-calibration",
            }:
                raise KeyError(identity)
            return
        entry = registry.get(identity)
        resources = [
            registry.path(entry, field)
            for field in [
                "file",
                "segmentation",
                "geometry",
                "operators",
                "metadata_file",
                "manifest",
                "design",
                "events",
                "surface",
            ]
            if getattr(entry, field)
        ]
        signature = [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in resources]
        if identity in revisions and signature != revisions[identity]:
            for method in [science.eeg, science.volume, science.source, science.analysis]:
                method.cache_clear()
        if revisions.get(identity) != signature and entry.manifest:
            manifest_path = registry.path(entry, "manifest")
            manifest = read_json(manifest_path)
            hashes = manifest.get("outputs_sha256", manifest.get("result_files_sha256", {}))
            for path in resources:
                if path == manifest_path or (
                    entry.surface and path == registry.path(entry, "surface")
                ):
                    continue
                if not path.is_relative_to(manifest_path.parent):
                    raise ValueError("Artifact not in sealed directory")
                expected = hashes.get(str(path.relative_to(manifest_path.parent)))
                if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError("Artifact checksum not verified")
        revisions[identity] = signature

    def result(
        identity: str,
        data: Any,
        warnings: list[str] | None = None,
        interpretation: State | None = None,
    ) -> Any:
        verify(identity)
        synthetic = identity.startswith("demo-") or registry.get(identity).synthetic
        return Result(
            dataset_id=identity,
            state=interpretation or (State.EXPLORATORY if synthetic else State.DESCRIPTIVE_ONLY),
            synthetic=synthetic,
            warnings=(
                warnings
                or ["Research use; numerical display is not anatomical or clinical validation"]
            )
            + (
                [
                    "Explicit configured spatial-unit override: "
                    + str(registry.get(identity).spatial_units_override)
                ]
                if not identity.startswith("demo-")
                and registry.get(identity).spatial_units_override
                else []
            ),
            provenance={
                "application_version": __version__,
                "soma_source_sha256": soma_hash,
                "adapter_source_sha256": adapter_hash,
                "analysis_parameters": {
                    "native_sample_analysis": True,
                    "Welch_segment_s": 1,
                    "Welch_overlap_fraction": 0.5,
                    "Morlet_cycles": 3,
                    "burst_band_hz": [8, 13],
                    "burst_fixed_thresholds_V": [3e-6, 5e-6],
                    "burst_min_cycles": 3,
                    "time_origin_s": data.tf_times_s[0] if isinstance(data, EEGAnalysis) else None,
                }
                if isinstance(data, EEGAnalysis)
                else {},
                "input_sha256": science.fingerprint(identity),
                "origin": "Soma deterministic synthetic generator, seed15042"
                if identity.startswith("demo-")
                else registry.get(identity).provenance,
                "confirmatory_claim_allowed": False,
            },
            data=data,
        )

    def calculate(request: JobRequest) -> Any:
        if not analysis_slots.acquire(blocking=False):
            raise HTTPException(429, "Analysis capacity reached; retry after the active window")
        try:
            verify(request.dataset_id)
            return result(
                request.dataset_id,
                science.analysis(
                    request.dataset_id, request.channel, request.start_s, request.duration_s
                ),
                [
                    "Window-local fixed burst thresholds; not rest-calibrated",
                    "TFR edges are not interpretable inside the reported guard; no ERD inference",
                ],
            )
        finally:
            analysis_slots.release()

    jobs = Jobs(calculate, jobs_root or Path("data/derived/explorer/jobs"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        yield
        jobs.close()
        science.close()

    app = FastAPI(title="Soma Explorer", version=__version__, lifespan=lifespan)
    from .protocols import router as protocol_router

    app.include_router(protocol_router(registry))
    from .human import router as human_router

    app.include_router(human_router(registry))
    from .eeg_benchmark import router as benchmark_router

    app.include_router(benchmark_router(registry))
    from .external_eeg import router as external_router

    app.include_router(external_router(registry))
    from .model_archive import router as model_archive_router

    app.include_router(model_archive_router(registry))
    from .external_validation import router as external_validation_router

    app.include_router(external_validation_router(registry))
    app.state.science, app.state.jobs, app.state.registry = science, jobs, registry
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ORIGINS),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def privacy(request: Request, call_next: Any) -> Any:
        origin = request.headers.get("origin")
        if (
            origin
            and origin not in ORIGINS
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        length = request.headers.get("content-length", "0")
        if not length.isdigit():
            return JSONResponse({"detail": "Invalid request length"}, status_code=400)
        if int(length) > 16384:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if request.method in {"POST", "DELETE"}:
            chunks = []
            total = 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > 16384:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Invalid scientific input, incompatible geometry or resource limit"},
            status_code=422,
        )

    @app.exception_handler(KeyError)
    @app.exception_handler(FileNotFoundError)
    async def missing(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": "Configured resource not available"}, status_code=404)

    def workflow_record(identity: str) -> tuple[Any, Any]:
        from soma.results.io import read_json as bounded_json
        from soma.workflow.examples import example
        from soma.workflow.model import Graph
        from soma.workflow.operations import builtins

        if identity in {"demo-workflow-" + f for f in ["eeg", "mri", "fmri", "source"]}:
            return example(identity.removeprefix("demo-workflow-")), None
        entry = registry.get(identity, "workflow")
        value = bounded_json(registry.path(entry))
        record = value if value.get("schema") == "soma.workflow.run/1" else None
        graph = Graph.from_dict(record["graph"] if record else value)
        builtins().validate(graph)
        return graph, record

    @app.get("/api/workflows")
    def workflows() -> Any:
        return [
            {"id": "demo-workflow-" + f, "label": "Synthetic " + f.upper(), "status": "NOT_RUN"}
            for f in ["eeg", "mri", "fmri", "source"]
        ] + [
            {"id": e.id, "label": e.label, "status": "RECORDED"}
            for e in registry.entries.values()
            if e.kind == "workflow"
        ]

    @app.get("/api/workflows/{identity}")
    def workflow_graph(identity: str) -> Any:
        from soma.workflow.view import graph_view

        graph, record = workflow_record(identity)
        return graph_view(graph, record)

    @app.get("/api/workflows/{identity}/lineage/{node}")
    def workflow_lineage(identity: str, node: str, downstream: bool = False) -> Any:
        from soma.workflow.privacy import redact_export

        graph, _ = workflow_record(identity)
        return redact_export(graph.lineage(node, downstream=downstream))

    @app.get("/api/catalog", response_model=Catalog)
    def catalog() -> Any:
        demos = [
            ("eeg", "Oscillatory EEG laboratory"),
            ("mri", "Asymmetric anatomical phantom"),
            ("source", "Prescribed source currents"),
            ("fmri", "Synthetic task GLM"),
        ]
        datasets = [
            Dataset(
                id=f"demo-{k}",
                label=label,
                kind=k,
                synthetic=True,
                state=State.EXPLORATORY,
                available=True,
                subjects=["synthetic"],
                sessions=["development"],
                runs=["1"],
            )
            for k, label in demos
        ]
        for entry in registry.entries.values():
            try:
                verify(entry.id)
                available = True
            except (ValueError, KeyError, FileNotFoundError):
                available = False
            datasets.append(
                Dataset(
                    id=entry.id,
                    label=entry.label,
                    kind=entry.kind,
                    synthetic=entry.synthetic,
                    state=State.DESCRIPTIVE_ONLY if available else State.NOT_AVAILABLE,
                    available=available,
                    subjects=[entry.subject],
                    sessions=[entry.session],
                    runs=[entry.run],
                )
            )
        return Catalog(
            datasets=datasets,
            version=__version__,
            inference_policy="14.1: human/feasible AR descriptive only",
        )

    @app.get("/api/eeg/{identity}/metadata", response_model=Result[EEGMeta])
    def eeg_meta(identity: str) -> Any:
        verify(identity)
        return result(identity, science.eeg(identity)[1])

    @app.get("/api/eeg/{identity}/window", response_model=Result[EEGWindow])
    def eeg_window(
        identity: str,
        channels: str = "C3",
        start_s: float = Query(0, ge=0),
        duration_s: float = Query(10, ge=0.1, le=30),
        points: int = Query(1200, ge=32, le=2048),
    ) -> Any:
        verify(identity)
        return result(
            identity,
            science.window(identity, channels.split(","), start_s, duration_s, points),
            ["Min/max envelope and bin means are display-only; analyses use original samples"],
        )

    @app.get("/api/eeg/{identity}/analysis", response_model=Result[EEGAnalysis])
    def eeg_analysis(
        identity: str,
        channel: str = "C3",
        start_s: float = Query(0, ge=0),
        duration_s: float = Query(10, ge=2, le=30),
    ) -> Any:
        return calculate(
            JobRequest(dataset_id=identity, channel=channel, start_s=start_s, duration_s=duration_s)
        )

    @app.get("/api/volumes/{identity}", response_model=Result[VolumeMeta])
    def volume_meta(identity: str) -> Any:
        verify(identity)
        return result(
            identity,
            science.volume_meta(identity),
            [
                "Neurological voxel-aligned planes; affine-derived coordinates; obliquity retained",
                "Categorical tissue labels do not validate skull/scalp conductors",
            ],
        )

    @app.get("/api/volumes/{identity}/slice", response_model=Result[Slice])
    def volume_slice(
        identity: str,
        plane: str = "axial",
        x: int = Query(0, ge=0),
        y: int = Query(0, ge=0),
        z: int = Query(0, ge=0),
    ) -> Any:
        verify(identity)
        return result(identity, science.slice(identity, plane, [x, y, z]))

    @app.get("/api/sources/{identity}/mesh", response_model=Result[MeshData])
    def mesh(identity: str) -> Any:
        verify(identity)
        data = science.mesh(identity)
        return result(identity, data, data.qc)

    @app.get("/api/sources/{identity}/series", response_model=Result[SourceSeries])
    def source_series(identity: str, index: int = Query(0, ge=0, le=9999)) -> Any:
        verify(identity)
        return result(identity, science.source_series(identity, index))

    @app.get("/api/fmri/{identity}", response_model=Result[dict[str, Any]])
    def fmri(identity: str, inference: Literal["descriptive"] = "descriptive") -> Any:
        verify(identity)
        return result(
            identity,
            science.fmri(identity),
            [
                "Descriptive only; no confirmatory bypass",
                "Human fMRIPrep derivatives and test–retest remain unavailable",
            ],
            interpretation=(
                State.NOT_AVAILABLE
                if not identity.startswith("demo-") and registry.get(identity).role == "bold"
                else None
            ),
        )

    def artifact(identity: str) -> Artifact:
        if identity == "demo-calibration":
            receipt_bytes = files("soma.resources").joinpath("calibration-demo.json").read_bytes()
            receipt = json.loads(receipt_bytes)
            row = next(
                r
                for r in receipt["calibration"]
                if r["case"] == "spatial-iid-independent-m343" and r["model"] == "ols"
            )
            return Artifact(
                state=State.EXPLORATORY,
                id=identity,
                title="Independent iid OLS calibration · Milestone14.1",
                metrics={
                    "any_BH_rejection": row["bh"]["any_rejection"],
                    "Wilson95": row["bh"]["Wilson95"],
                    "families": row["n_realizations"],
                },
                parameters={"seed": 1411000, "n": 100, "voxels": 343, "q": 0.05},
                compatibility={
                    "units": "probability",
                    "estimand": "global_null_any_BH_rejection",
                    "frame": "nonspatial",
                    "processing": "iid-OLS-fixed-X-m343",
                },
                checksums={
                    "receipt_sha256": receipt["source_receipt_sha256"],
                    "packaged_excerpt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                    "protocol_sha256": receipt["protocol_sha256"],
                },
                figures=[],
                warnings=["Recorded synthetic benchmark; not human calibration"],
            )
        verify(identity)
        entry = registry.get(identity, "experiment")
        path = registry.path(entry)
        data = read_json(path)
        if not isinstance(data, dict):
            raise ValueError("Experiment receipt must be an object")
        if "schema_name" in data:
            try:
                envelope, _ = load_result(path)
            except (SchemaError, OSError, ValueError) as error:
                reason = str(error)
                status = (
                    "UNSUPPORTED_VERSION" if "Unsupported schema" in reason else "INVALID_ARTIFACT"
                )
                return Artifact(
                    id=identity,
                    title=entry.label,
                    state=State.INVALID,
                    schema_name=sanitize(str(data.get("schema_name", "unknown"))),
                    schema_version=sanitize(str(data.get("schema_version", "unknown"))),
                    validation_status=status,
                    migration_status="NOT_APPLIED",
                    metrics={},
                    parameters={},
                    compatibility={},
                    checksums={},
                    figures=[],
                    warnings=[status + ": " + reason, "No numerical view or export is permitted"],
                )
            domain = envelope["payload"]["domain"]
            return Artifact(
                id=identity,
                title=entry.label,
                state=State(envelope["interpretation_state"]),
                schema_name=envelope["schema_name"],
                schema_version=envelope["schema_version"],
                validation_status="FORMAT_AND_INTEGRITY_VERIFIED",
                migration_status="MIGRATED_READ_ONLY"
                if "migration" in envelope
                else "NATIVE_SCHEMA",
                result_envelope=sanitize(envelope),
                metrics=sanitize(
                    {
                        "values": envelope["payload"]["values"],
                        "domain": domain,
                        "array_descriptors": envelope["payload"]["arrays"],
                    }
                ),
                parameters=sanitize(envelope.get("parameters", {})),
                compatibility={
                    "units": json.dumps(envelope.get("units", {}), sort_keys=True),
                    "estimand": str(envelope.get("statistical_estimand", "unrecorded")),
                    "frame": str(envelope.get("spatial_reference")),
                    "processing": json.dumps(envelope.get("method", {}), sort_keys=True),
                },
                checksums={
                    "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "metadata_sha256": envelope["checksums"]["metadata"],
                },
                figures=[],
                warnings=[
                    "Schema/integrity checks do not certify scientific validity",
                    "Display metadata sanitized; checksums identify the original artifact",
                ],
            )
        parameters = {}
        if entry.manifest:
            sealed = read_json(registry.path(entry, "manifest"))
            parameters = {
                "analysis_parameters": sanitize(sealed.get("parameters", {})),
                "libraries": sanitize(sealed.get("libraries", {})),
                "application_version": sanitize(sealed.get("application_version")),
                "random_seed": sealed.get("random_seed"),
                "code_sha256": sanitize(sealed.get("source_tree_sha256")),
            }
        figures = [f"/api/experiments/{identity}/figures/{i}" for i in range(len(entry.figures))]
        return Artifact(
            state=State.EXPLORATORY if entry.synthetic else State.DESCRIPTIVE_ONLY,
            id=identity,
            title=entry.label,
            metrics=sanitize(data),
            parameters=parameters,
            compatibility=entry.compatibility,
            checksums={
                "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **(
                    {
                        "manifest_sha256": hashlib.sha256(
                            registry.path(entry, "manifest").read_bytes()
                        ).hexdigest()
                    }
                    if entry.manifest
                    else {}
                ),
            },
            figures=figures,
            warnings=[entry.provenance, "Historical artifact; not modified by Explorer"],
        )

    @app.get("/api/experiments", response_model=list[Artifact])
    def experiments(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)) -> Any:
        ids = [
            "demo-calibration",
            *[e.id for e in registry.entries.values() if e.kind == "experiment"],
        ]
        return [artifact(i) for i in ids[offset : offset + limit]]

    @app.post("/api/experiments/compare", response_model=Comparison)
    def compare(request: CompareRequest) -> Any:
        items = [artifact(i) for i in request.ids]
        if any(a.schema_name is not None for a in items):
            if not all(a.validation_status == "FORMAT_AND_INTEGRITY_VERIFIED" for a in items):
                raise HTTPException(
                    409,
                    "Invalid, unsupported or legacy metadata cannot be compared "
                    "as versioned results",
                )
            original = [
                load_result(registry.path(registry.get(a.id, "experiment")))[0] for a in items
            ]
            judgments = [compare_results(original[0], value) for value in original[1:]]
            if any(not j["compatible"] for j in judgments):
                raise HTTPException(409, {"scientific_compatibility": judgments})
            return {"compatible": True, "artifacts": items}
        keys = {"units", "estimand", "frame", "processing"}
        if any(set(a.compatibility) != keys for a in items) or any(
            a.compatibility != items[0].compatibility for a in items[1:]
        ):
            raise HTTPException(
                409, "Units, estimands, frames and processing definitions must match"
            )
        return {"compatible": True, "artifacts": items}

    @app.get("/api/experiments/{identity}/figures/{index}")
    def figure(identity: str, index: int) -> Any:
        entry = registry.get(identity, "experiment")
        if not 0 <= index < len(entry.figures):
            raise KeyError(index)
        path = registry.resolve(entry, entry.figures[index])
        if path.suffix.lower() != ".png" or path.stat().st_size > 4 * 1024**2:
            raise ValueError("Only bounded approved PNG artifacts")
        if entry.manifest:
            manifest_path = registry.path(entry, "manifest")
            sealed = read_json(manifest_path)
            hashes = sealed.get("outputs_sha256", sealed.get("result_files_sha256", {}))
            if not path.is_relative_to(manifest_path.parent):
                raise ValueError("Figure outside sealed artifact")
            expected = hashes.get(str(path.relative_to(manifest_path.parent)))
            if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Figure checksum mismatch")
        if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/experiments/{identity}/export")
    def export(identity: str, format: str = Query("json", pattern="^(json|csv)$")) -> Any:
        a = artifact(identity)
        if a.state == State.INVALID:
            raise HTTPException(422, "Invalid or unsupported artifact cannot be exported")
        if format == "json":
            return JSONResponse(
                a.model_dump(),
                headers={"Content-Disposition": 'attachment; filename="soma-result.json"'},
            )
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(["metric", "value"])
        exported_metrics = {
            **a.metrics,
            "_interpretation_state": str(a.state),
            "_warnings": a.warnings,
            "_compatibility": a.compatibility,
            "_checksums": a.checksums,
        }
        for key, value in exported_metrics.items():
            # Spreadsheet formula injection protection; nested values are JSON.
            def safe(v: str) -> str:
                return "'" + v if v.startswith(("=", "+", "-", "@")) else v

            writer.writerow([safe(key), safe(json.dumps(value))])
        return Response(
            text.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="soma-result.csv"'},
        )

    @app.get("/api/qc", response_model=QCReport)
    def qc() -> Any:
        return {
            "state": "INDETERMINATE",
            "human_preprocessing": "NOT_AVAILABLE",
            "human_retest": "NOT_AVAILABLE",
            "clinical_validity": False,
            "warnings": [
                "No validated human fMRIPrep derivatives",
                "Tissue validation is not conductor validation",
                "Inverse reconstructions are not anatomical ground truth",
            ],
            "inference_policy": "Milestone14.1 guard: descriptive human results only",
        }

    @app.post("/api/jobs", response_model=Job, status_code=202)
    def submit(request: JobRequest) -> Any:
        verify(request.dataset_id)
        return jobs.submit(request)

    @app.get("/api/jobs/{identity}", response_model=Job)
    def job(identity: str) -> Any:
        return jobs.get(identity)

    @app.delete("/api/jobs/{identity}", response_model=Job)
    def cancel(identity: str) -> Any:
        return jobs.cancel(identity)

    return app


app = create_app()
