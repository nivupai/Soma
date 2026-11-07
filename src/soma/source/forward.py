"""MNE EEG forward adapter with explicit source identities and reference state."""

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import mne
import numpy as np
from numpy.typing import NDArray

from soma.core.provenance import sha256
from soma.geometry import Frame, Points, SourceCoordinates
from soma.simulations.calibration import atomic_json
from soma.source.noise import average_projector
from soma.source.template import Template


@dataclass
class ForwardModel:
    native_free: Any
    info: Any
    geometry: dict[str, Any]
    anatomy: dict[str, Any]
    orientation: Literal["fixed", "free"] = "fixed"
    preparation_runtime_s: float | None = None

    def __post_init__(self) -> None:
        fwd = self.native_free
        if self.orientation not in ("fixed", "free"):
            raise ValueError("Orientation must be fixed or free")
        if not fwd["surf_ori"] or fwd["sol"]["data"].shape[1] != 3 * fwd["nsource"]:
            raise ValueError("Native forward must use a free, surface-local orientation basis")
        if fwd["sol"]["row_names"] != self.info["ch_names"]:
            raise ValueError("Forward/info channel order differs")
        if int(fwd["coord_frame"]) != 4:
            raise ValueError("Expected forward in MNE head coordinates")
        self.native_fixed = mne.convert_forward_solution(
            fwd, surf_ori=True, force_fixed=True, use_cps=False, copy=True, verbose=False
        )
        self.projector = average_projector(len(self.info["ch_names"]))
        selected = self.native_fixed if self.orientation == "fixed" else fwd
        self.unreferenced = np.asarray(selected["sol"]["data"], dtype=float)
        self.matrix = self.projector @ self.unreferenced
        if not np.isfinite(self.matrix).all():
            raise ValueError("Nonfinite lead field")
        self.vertices = [np.array(s["vertno"], dtype=int) for s in fwd["src"]]
        ids = tuple(
            (hemi, int(vertex))
            for hemi, vs in zip(("lh", "rh"), self.vertices, strict=True)
            for vertex in vs
        )
        self.coordinates = SourceCoordinates(Points(fwd["source_rr"], Frame.HEAD), ids)
        local_normal = fwd["sol"]["data"][:, 2::3]
        if not np.allclose(local_normal, self.native_fixed["sol"]["data"], rtol=1e-6, atol=1e-9):
            raise ValueError("Fixed normals do not match free forward normal columns")

    def require_vertices(self, vertices: list[NDArray[np.int64]]) -> None:
        if len(vertices) != 2 or any(
            not np.array_equal(a, b) for a, b in zip(vertices, self.vertices, strict=True)
        ):
            raise ValueError("Source vertex ordering differs from the forward model")

    def diagnostics(self) -> dict[str, Any]:
        s = np.linalg.svd(self.matrix, compute_uv=False)
        keep = s > s[0] * max(self.matrix.shape) * np.finfo(float).eps
        return {
            "shape": list(self.matrix.shape),
            "rank": int(keep.sum()),
            "singular_values": s.tolist(),
            "retained_condition": float(s[0] / s[keep][-1]),
            "underdetermined": self.matrix.shape[1] > int(keep.sum()),
            "orientation": self.orientation,
            "use_cps": False,
            "units": "V / (A m)",
            "coordinate_frame": "head_metres",
            "reference": "average",
            "channels": self.info["ch_names"],
            "source_identifiers": self.coordinates.identifiers,
            "geometry": self.geometry,
            "anatomy": self.anatomy,
            "reference_residual_relative": float(
                np.linalg.norm(self.matrix.sum(axis=0)) / np.linalg.norm(self.matrix)
            ),
        }


def build_forward(
    template: Template,
    names: list[str],
    *,
    spacing: str = "ico3",
    orientation: Literal["fixed", "free"] = "fixed",
    cache: Path | None = None,
) -> ForwardModel:
    """Compute a genuine three-shell BEM forward, or read an explicit cache.

    Cache metadata binds channel identities, anatomy hashes and geometry. Rebuild
    is required on any mismatch; native matrices alone cannot establish identity.
    """
    import json

    started = time.perf_counter()
    anatomy = template.inspect()
    src = template.source_space(spacing)
    anatomy["source_space_sha256"] = sha256(template.root / "bem" / f"soma-{spacing}-white-src.fif")
    anatomy["spacing"] = spacing
    info, geometry = template.sensor_info(names)
    identity = {
        "anatomy": anatomy,
        "channels": names,
        "spacing": spacing,
        "mindist_mm": 5,
        "montage": "fsaverage_1005",
        "mne": mne.__version__,
        "numpy": np.__version__,
        "builder_code_sha256": sha256(Path(__file__)),
        "template_adapter_sha256": sha256(Path(__file__).with_name("template.py")),
    }
    metadata = None if cache is None else cache.with_suffix(".json")
    if cache is not None and cache.exists():
        if (
            metadata is None
            or not metadata.exists()
            or json.loads(metadata.read_text()).get("identity") != identity
            or json.loads(metadata.read_text()).get("forward_sha256") != sha256(cache)
        ):
            raise ValueError("Forward cache identity mismatch")
        native = mne.read_forward_solution(cache, verbose=False)
    else:
        native = mne.make_forward_solution(
            info,
            trans=template.transform.to_mne(),
            src=src,
            bem=template.bem,
            meg=False,
            eeg=True,
            mindist=5,
            n_jobs=1,
            verbose=False,
        )
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=cache.parent, prefix=".soma-fwd-") as staging:
                temporary = Path(staging) / "native-fwd.fif"
                mne.write_forward_solution(temporary, native, overwrite=False, verbose=False)
                os.replace(temporary, cache)
            assert metadata is not None
            atomic_json(metadata, {"identity": identity, "forward_sha256": sha256(cache)})
    native = mne.convert_forward_solution(
        native, surf_ori=True, force_fixed=False, use_cps=False, copy=True, verbose=False
    )
    return ForwardModel(native, info, geometry, anatomy, orientation, time.perf_counter() - started)
