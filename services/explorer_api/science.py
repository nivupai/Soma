"""Bounded adapters to Soma. Display reduction never feeds scientific analysis."""

import hashlib
import math
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import mne
import nibabel as nib
import numpy as np
import pandas as pd
from mne.time_frequency import tfr_array_morlet
from neurodsp.filt import filter_signal

from soma.datasets.eegbci import event_meanings
from soma.experiments.fmri_simulation import simulate
from soma.experiments.source_simulation import source_waveforms
from soma.geometry import Frame, Points, Transform
from soma.imaging.phantoms import asymmetric, ellipsoid
from soma.sdk.eeg import BANDS, Signal, WelchConfig, welch
from soma.sdk.fmri import Contrast, ModelConfig, contrast, fit
from soma.sdk.imaging import extract_surface, load_nifti
from soma.signal.bursts import calibrated_detector, intervals
from soma.signal.synthetic import synthetic
from soma.source.resolution import Resolution, spatial_metrics

from .models import EEGAnalysis, EEGMeta, EEGWindow, MeshData, Slice, SourceSeries, VolumeMeta
from .registry import Registry, read_json, sanitize


def archive(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 64 * 1024**2:
            raise ValueError("Array archive exceeds 64 MiB decoded limit")
    with np.load(path, allow_pickle=False) as a:
        result = {k: a[k] for k in a.files}
    if any(v.dtype.kind not in "biuf" or not np.isfinite(v).all() for v in result.values()):
        raise ValueError("Only finite numerical arrays accepted")
    return result


class Science:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    @lru_cache(maxsize=4)  # noqa: B019 — bounded process cache, cleared on shutdown
    def eeg(self, identity: str) -> tuple[Any, EEGMeta]:
        if identity == "demo-eeg":
            signals = [
                synthetic(k, duration=60, seed=15042 + i)
                for i, k in enumerate(["burst", "combined", "modulated"])
            ]
            data = np.stack([s.values for s in signals])
            events: list[dict[str, Any]] = [
                {
                    "onset": t,
                    "duration": 6,
                    "code": "T1" if i % 2 == 0 else "T2",
                    "label": "synthetic left hand imagery"
                    if i % 2 == 0
                    else "synthetic right hand imagery",
                }
                for i, t in enumerate([8, 20, 32, 44])
            ]
            return data, EEGMeta(
                channels=["C3", "Cz", "C4"],
                fs_hz=160,
                duration_s=60,
                reference="Synthetic amplitudes, no physical reference",
                events=events,
                quality=["Synthetic illustration; no participant physiology"],
            )
        entry = self.registry.get(identity, "eeg")
        raw = mne.io.read_raw_edf(self.registry.path(entry), preload=False, verbose=False)
        if raw.info["sfreq"] > 2048 or len(raw.ch_names) > 256:
            raise ValueError("Recording exceeds supported resource bounds")
        meanings = event_meanings(int(entry.run)) if entry.run.isdigit() else {}
        events = [
            {
                "onset": float(o),
                "duration": float(d),
                "code": str(c),
                "label": meanings.get(str(c), str(c)),
            }
            for o, d, c in zip(
                raw.annotations.onset,
                raw.annotations.duration,
                raw.annotations.description,
                strict=True,
            )
        ]
        return raw, EEGMeta(
            channels=raw.ch_names,
            fs_hz=float(raw.info["sfreq"]),
            duration_s=raw.n_times / raw.info["sfreq"],
            reference="As recorded; no rereference",
            events=events[:1000],
            quality=["Raw recording; artifacts not removed"],
        )

    def samples(
        self, identity: str, channels: list[str], start: float, duration: float
    ) -> tuple[np.ndarray[Any, Any], EEGMeta, int, int]:
        if not np.isfinite([start, duration]).all() or start < 0 or not 0.1 <= duration <= 30:
            raise ValueError("Window must be finite, start>=0 and .1–30 seconds")
        if not 1 <= len(channels) <= 8 or len(set(channels)) != len(channels):
            raise ValueError("Select 1–8 unique channels")
        if identity != "demo-eeg":
            self.registry.get(identity, "eeg")  # Revalidate symlinks even on cached objects.
        raw, meta = self.eeg(identity)
        if any(c not in meta.channels for c in channels):
            raise ValueError("Unknown recording channel")
        a, b = round(start * meta.fs_hz), round((start + duration) * meta.fs_hz)
        if start + duration > meta.duration_s or b - a < 2:
            raise ValueError("Window outside recording")
        ids = [meta.channels.index(c) for c in channels]
        data = (
            raw[ids, a:b]
            if isinstance(raw, np.ndarray)
            else raw.get_data(picks=ids, start=a, stop=b)
        )
        if not np.isfinite(data).all():
            raise ValueError("Nonfinite recording window")
        return np.asarray(data), meta, a, b

    def window(
        self, identity: str, channels: list[str], start: float, duration: float, points: int
    ) -> EEGWindow:
        data, meta, a, b = self.samples(identity, channels, start, duration)
        step = max(1, math.ceil(data.shape[1] / points))
        bins = [data[:, i : i + step] for i in range(0, data.shape[1], step)]
        return EEGWindow(
            times_s=((a + np.arange(len(bins)) * step) / meta.fs_hz).tolist(),
            channels=channels,
            values_V=np.stack([x.mean(axis=1) for x in bins], axis=1).tolist(),
            lower_V=np.stack([x.min(axis=1) for x in bins], axis=1).tolist(),
            upper_V=np.stack([x.max(axis=1) for x in bins], axis=1).tolist(),
            fs_hz=meta.fs_hz,
            start_sample=a,
            stop_sample=b,
        )

    @lru_cache(maxsize=16)  # noqa: B019 — bounded process cache, cleared on shutdown
    def analysis(self, identity: str, channel: str, start: float, duration: float) -> EEGAnalysis:
        if duration < 2:
            raise ValueError("Analysis requires at least2s")
        data, meta, first_sample, _ = self.samples(identity, [channel], start, duration)
        # Timestamps follow consumed samples, not a fractional requested offset.
        start = first_sample / meta.fs_hz
        values, fs = data[0], meta.fs_hz
        segment = round(fs)
        spectrum = welch(Signal(values, fs, channel), WelchConfig(segment, segment // 2))
        frequencies = np.arange(8.0, 31.0, 2.0)
        power = tfr_array_morlet(
            values[None, None, :],
            fs,
            frequencies,
            n_cycles=3,
            output="power",
            decim=max(1, len(values) // 160),
            n_jobs=1,
            verbose=False,
        )[0, 0]
        filtered = filter_signal(values, fs, "bandpass", (8, 13), n_cycles=3, remove_edges=False)
        detected = calibrated_detector(np.asarray(filtered), fs, 3e-6, 5e-6, 3 / 10.5)
        guard = min(1.0, duration / 4)
        detected[: round(guard * fs)] = False
        detected[-round(guard * fs) :] = False
        return EEGAnalysis(
            channel=channel,
            frequencies_hz=spectrum.frequencies.tolist(),
            density_V2_Hz=spectrum.density.tolist(),
            band_power_V2={k: spectrum.band_power(*v) for k, v in BANDS.items()},
            tf_times_s=(
                start + np.arange(power.shape[1]) * max(1, len(values) // 160) / fs
            ).tolist(),
            tf_frequencies_hz=frequencies.tolist(),
            tf_power_V2=power.tolist(),
            bursts_s=[[start + a / fs, start + b / fs] for a, b in intervals(detected)],
            n_analysis_samples=len(values),
            edge_guard_s=guard,
        )

    @lru_cache(maxsize=1)  # noqa: B019 — bounded process cache, cleared on shutdown
    def demo_anatomy(self) -> tuple[Any, Any]:
        v = asymmetric(spacing_m=(0.002, 0.003, 0.004), seed=15042)
        image = nib.Nifti1Image(v.array(), v.affine_m * np.array([1000, 1000, 1000, 1])[:, None])
        image.header.set_xyzt_units("mm")
        xyz = np.indices(image.shape)
        center = (np.array(image.shape) - 1) / 2
        r = np.sqrt(sum(((xyz[i] - center[i]) / (center[i] * 0.8)) ** 2 for i in range(3)))
        labels = np.where(r < 0.6, 1, np.where(r < 1, 2, 0)).astype(np.uint8)
        return image, labels

    @lru_cache(maxsize=1)  # noqa: B019 — bounded process cache, cleared on shutdown
    def demo_fmri(self) -> dict[str, Any]:
        run, _ = simulate(15042)
        fitted = fit(
            run,
            ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend")),
        )
        estimate = contrast(fitted, Contrast("task", {"task": 1}))
        return {
            "image": estimate.maps["effect_size"],
            "design": fitted.design.to_numpy().tolist(),
            "columns": list(fitted.design),
            "events": run.events.to_dict("records"),
            "metadata": estimate.metadata,
            "residual": fitted.diagnostics,
            "tr_s": run.tr,
            "n_scans": run.n_scans,
            "roi": {
                "whole_mask_mean_effect": float(estimate.maps["effect_size"].get_fdata().mean())
            },
        }

    @lru_cache(maxsize=4)  # noqa: B019 — bounded process cache, cleared on shutdown
    def volume(self, identity: str) -> tuple[Any, Any, str, str]:
        if identity == "demo-mri":
            image, seg = self.demo_anatomy()
            return image, seg, "synthetic-RAS", "arbitrary intensity"
        if identity == "demo-fmri":
            return self.demo_fmri()["image"], None, "synthetic-RAS", "BOLD effect units"
        entry = self.registry.get(identity)
        if entry.kind not in {"mri", "fmri"}:
            raise ValueError("Not a volume")
        v = load_nifti(
            self.registry.path(entry), units_override=entry.spatial_units_override
        )  # Reject ambiguous geometry/unknown units.
        if np.prod(v.shape) > 32_000_000 or len(v.shape) != 3:
            raise ValueError("Volume exceeds32M voxels or is not3D")
        affine = v.affine_m * np.array([1000, 1000, 1000, 1])[:, None]
        image = nib.as_closest_canonical(nib.Nifti1Image(v.array(), affine))
        seg = None
        if entry.segmentation:
            sv = load_nifti(self.registry.path(entry, "segmentation"), kind="labels")
            si = nib.as_closest_canonical(
                nib.Nifti1Image(sv.array(), sv.affine_m * np.array([1000, 1000, 1000, 1])[:, None])
            )
            if si.shape != image.shape or not np.allclose(si.affine, image.affine, atol=1e-5):
                raise ValueError("Segmentation grid/frame not aligned; no silent resampling")
            seg = np.asarray(si.dataobj)
        return image, seg, entry.frame, entry.units

    def volume_meta(self, identity: str) -> VolumeMeta:
        image, seg, frame, unit = self.volume(identity)
        data = np.asarray(image.dataobj)
        if not np.isfinite(data).all():
            raise ValueError("Nonfinite volume")
        return VolumeMeta(
            shape=list(image.shape),
            affine_mm=image.affine.tolist(),
            spacing_mm=nib.affines.voxel_sizes(image.affine).tolist(),
            orientation=list(nib.aff2axcodes(image.affine)),
            frame=frame,
            units=unit,
            intensity_range=np.percentile(data, [1, 99]).tolist(),
            oblique=bool(np.max(nib.affines.obliquity(image.affine)) > 1e-4),
            labels={str(int(k)): f"Label{int(k)}" for k in np.unique(seg)}
            if seg is not None
            else {},
        )

    def slice(self, identity: str, plane: str, voxel: list[int]) -> Slice:
        image, seg, _, unit = self.volume(identity)
        axes = {"axial": (0, 1, 2), "coronal": (0, 2, 1), "sagittal": (1, 2, 0)}
        if (
            plane not in axes
            or len(voxel) != 3
            or any(not 0 <= v < n for v, n in zip(voxel, image.shape, strict=True))
        ):
            raise ValueError("Invalid slice plane/voxel")
        u, v, fixed = axes[plane]
        step = max(1, math.ceil(max(image.shape) / 128))
        order = (u, v, fixed)
        # Row0 is high v: neurological convention (+RAS x to screen right).
        values = np.transpose(np.asarray(image.dataobj), order)[::step, ::step, voxel[fixed]].T[
            ::-1
        ]
        labels = (
            np.transpose(seg, order)[::step, ::step, voxel[fixed]].T[::-1]
            if seg is not None
            else None
        )
        transform = np.zeros((4, 4))
        transform[3, 3] = 1
        transform[u, 0] = step
        transform[v, 1] = -step
        transform[v, 3] = ((image.shape[v] - 1) // step) * step
        transform[fixed, 3] = voxel[fixed]
        code = nib.aff2axcodes(image.affine)
        opposite = {"R": "L", "A": "P", "S": "I", "L": "R", "P": "A", "I": "S"}
        world = nib.affines.apply_affine(image.affine, voxel)
        return Slice(
            plane=plane,
            index=voxel[fixed],
            width=values.shape[1],
            height=values.shape[0],
            values=values.astype(float).tolist(),
            labels=labels.astype(int).tolist() if labels is not None else None,
            voxel=voxel,
            world_mm=world.tolist(),
            label=int(seg[tuple(voxel)]) if seg is not None else None,
            pixel_to_world_mm=(image.affine @ transform).tolist(),
            horizontal_labels=[opposite[code[u]], code[u]],
            vertical_labels=[code[v], opposite[code[v]]],
            stride=step,
            overlay_units=unit if identity.endswith("fmri") else None,
        )

    @lru_cache(maxsize=4)  # noqa: B019 — bounded process cache, cleared on shutdown
    def source(self, identity: str) -> dict[str, Any]:
        if identity == "demo-source":
            mesh = extract_surface(ellipsoid(0.004))
            xyz = mesh.vertices.xyz * 1000
            currents, _ = source_waveforms("bursts", 160, 4, 1e-8)
            points = xyz[:: max(1, len(xyz) // 80)]
            return {
                "vertices": xyz,
                "faces": mesh.faces,
                "points": points,
                "electrodes": np.empty((0, 3)),
                "estimate": np.tile(currents, (math.ceil(len(points) / 2), 1))[: len(points)],
                "times": np.arange(640) / 160,
                "frame": "synthetic-RAS",
                "units": "A m",
                "qc": ["Analytic phantom/currents; not a cortical inverse reconstruction"],
                "diagnostics": {
                    "geometry": "Soma ellipsoid marching cubes; no decimation",
                    "anatomical_readiness": "synthetic only",
                },
            }
        entry = self.registry.get(identity, "source")
        a = archive(self.registry.path(entry))
        if "estimate" not in a or "times_s" not in a or a["estimate"].ndim != 2:
            raise ValueError("Expected source estimate[source,time] and times_s")
        estimate = a["estimate"]
        if a["times_s"].ndim != 1 or not np.all(np.diff(a["times_s"]) > 0):
            raise ValueError("Source time coordinates must be strictly increasing")
        if (
            estimate.shape[0] > 10000
            or estimate.shape[1] > 10000
            or len(a["times_s"]) != estimate.shape[1]
        ):
            raise ValueError("Source matrix shape unsupported")
        geometry = archive(self.registry.path(entry, "geometry")) if entry.geometry else {}
        points = geometry.get("source_head_m", np.empty((0, 3))) * 1000
        if len(points) and (entry.frame != "MNE-head" or len(points) != len(estimate)):
            raise ValueError("Source geometry identity/frame mismatch")
        display_vertices = np.empty((0, 3))
        display_faces = np.empty((0, 3), dtype=int)
        if entry.surface:
            spaces = mne.read_source_spaces(self.registry.path(entry, "surface"), verbose=False)
            selected, faces, offset = [], [], 0
            for space, key in zip(spaces, ["lh_vertices", "rh_vertices"], strict=True):
                if int(space["coord_frame"]) != 5 or not np.array_equal(
                    space["vertno"], geometry[key]
                ):
                    raise ValueError("Surface/source vertex ordering or MRI frame mismatch")
                ids = space["vertno"]
                remap = {int(vertex): index + offset for index, vertex in enumerate(ids)}
                faces.extend([[remap[int(i)] for i in tri] for tri in space["use_tris"]])
                selected.append(space["rr"][ids])
                offset += len(ids)
            transform = Transform(Frame.MRI, Frame.HEAD, geometry["mri_to_head"])
            transformed = transform.apply(Points(np.vstack(selected), Frame.MRI)).xyz
            if not np.allclose(transformed * 1000, points, atol=1e-4, rtol=0):
                raise ValueError("Cortical mesh/source coregistration differs")
            display_vertices = transformed * 1000
            display_faces = np.asarray(faces, dtype=int)
        operators = archive(self.registry.path(entry, "operators")) if entry.operators else None
        if operators is not None:
            if operators["assumed_forward"].shape[1] != len(estimate):
                raise ValueError("Leadfield/source ordering size mismatch")
            if self.registry.path(entry, "operators").parent != self.registry.path(entry).parent:
                raise ValueError("Operators must belong to the same sealed artifact directory")
        extra = (
            sanitize(read_json(self.registry.path(entry, "metadata_file")))
            if entry.metadata_file
            else {}
        )
        return {
            "operators": operators,
            "vertices": display_vertices,
            "faces": display_faces,
            "points": points,
            "electrodes": geometry.get("sensor_head_m", np.empty((0, 3))) * 1000,
            "estimate": estimate,
            "times": a["times_s"],
            "frame": entry.frame,
            "units": entry.units,
            "qc": [
                entry.provenance,
                "Visualization does not validate conductor anatomy or localization",
            ],
            "diagnostics": {
                "source_count": len(estimate),
                "display_connectivity": "Source-space use_tris; reduced cortical mesh, not BEM",
                "mri_to_head_m": geometry.get("mri_to_head", np.eye(4)).tolist()
                if entry.surface
                else None,
                "leadfield": extra,
                "geometry": "original source/electrode points; no invented cortical faces",
            },
        }

    def mesh(self, identity: str) -> MeshData:
        a = self.source(identity)
        return MeshData(
            vertices_mm=a["vertices"].tolist(),
            faces=a["faces"].tolist(),
            values=np.max(abs(a["estimate"]), axis=1).tolist(),
            points_mm=a["points"].tolist(),
            electrode_points_mm=a["electrodes"].tolist(),
            frame=a["frame"],
            units="mm",
            layers=["surface", "sources", "electrodes"],
            qc=a["qc"],
            render_geometry="Original bounded geometry; not a numerical conductor model",
            diagnostics=a["diagnostics"],
        )

    def source_series(self, identity: str, index: int) -> SourceSeries:
        a = self.source(identity)
        if not 0 <= index < len(a["estimate"]):
            raise ValueError("Source index outside model")
        stride = max(1, math.ceil(len(a["times"]) / 2048))
        point_spread = None
        diagnostics = {}
        if a.get("operators") is not None:
            op = a["operators"]
            resolution = Resolution(op["primary_inverse_kernel"], op["assumed_forward"])
            psf = resolution.psf([index])[:, 0]
            point_spread = psf.tolist()
            if len(a["points"]):
                diagnostics = spatial_metrics(psf, index, a["points"] / 1000)
        return SourceSeries(
            source_index=index,
            times_s=a["times"][::stride].tolist(),
            values=a["estimate"][index, ::stride].tolist(),
            units=a["units"],
            point_mm=a["points"][index].tolist() if len(a["points"]) else None,
            point_spread=point_spread,
            diagnostics=diagnostics,
        )

    def fmri(self, identity: str) -> dict[str, Any]:
        if identity == "demo-fmri":
            a = self.demo_fmri()
            return {k: sanitize(v) for k, v in a.items() if k != "image"}
        entry = self.registry.get(identity, "fmri")
        if entry.role == "bold":
            image: Any = nib.load(self.registry.path(entry), mmap="r")
            return {
                "metadata": {
                    "shape": list(image.shape),
                    "tr_s": float(image.header.get_zooms()[3]),
                    "preprocessing": "raw BOLD; derivatives unavailable",
                    "confirmatory_claim_allowed": False,
                },
                "design": [],
                "columns": [],
                "events": [],
                "roi": {},
                "residual": {},
                "limitations": ["Raw BOLD cannot be used as a validated contrast map"],
            }
        self.volume_meta(identity)
        for field in ["design", "events"]:
            if (
                getattr(entry, field)
                and self.registry.path(entry, field).stat().st_size > 4 * 1024**2
            ):
                raise ValueError("Tabular metadata exceeds4MiB")
        design = (
            pd.read_csv(self.registry.path(entry, "design"), sep="\t", nrows=2001)
            if entry.design
            else pd.DataFrame()
        )
        if design.shape[0] > 2000 or design.shape[1] > 64:
            raise ValueError("Design exceeds bounded display dimensions")
        events = (
            pd.read_csv(self.registry.path(entry, "events"), sep="\t", nrows=1000).to_dict(
                "records"
            )
            if entry.events
            else []
        )
        imported = (
            sanitize(read_json(self.registry.path(entry, "metadata_file")))
            if entry.metadata_file
            else {}
        )
        return {
            "metadata": {
                "preprocessing": "historical operator-selected artifact",
                "inference_policy": "Milestone14.1: descriptive only",
                "confirmatory_claim_allowed": False,
                "noise_model": "inspect original manifest",
            },
            "design": design.to_numpy().tolist(),
            "columns": list(design),
            "events": events,
            "roi": {},
            "residual": imported,
            "limitations": [
                entry.provenance,
                "No new model fit; unavailable confounds/design are not reconstructed",
            ],
        }

    def fingerprint(self, identity: str) -> str:
        if identity.startswith("demo-"):
            return hashlib.sha256((identity + ":15042:v1").encode()).hexdigest()
        entry = self.registry.get(identity)
        path = self.registry.path(entry)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def close(self) -> None:
        for method in [
            self.eeg,
            self.analysis,
            self.volume,
            self.source,
            self.demo_anatomy,
            self.demo_fmri,
        ]:
            method.cache_clear()
