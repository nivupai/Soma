"""NIfTI-1/2 affine semantics and explicit conflict/unknown-unit policies."""

import warnings
from pathlib import Path
from typing import Any, Literal

import nibabel as nib
import numpy as np

from soma.core.provenance import sha256
from soma.geometry.coordinates import validate_affine
from soma.imaging.volumes import Volume


class _FrameProxy:
    def __init__(self, proxy: Any, frame: int) -> None:
        self.proxy, self.frame = proxy, frame
        self.shape, self.dtype = proxy.shape[:3], proxy.dtype

    def __array__(self, dtype: Any = None, copy: bool | None = None) -> Any:
        result = np.asanyarray(self.proxy[..., self.frame], dtype=dtype)
        return result.copy() if copy else result


def load_nifti(
    path: Path,
    *,
    frame: int | None = None,
    policy: Literal["error", "nibabel", "qform", "sform"] = "error",
    units_override: str | None = None,
    kind: Literal["intensity", "labels"] = "intensity",
) -> Volume:
    image: Any = nib.load(path, mmap="r")
    if not isinstance(image, (nib.Nifti1Image, nib.Nifti2Image)):
        raise ValueError("Only NIfTI-1 and NIfTI-2 are supported")
    header = image.header
    if tuple(header.get_data_shape()) != tuple(image.dataobj.shape):
        raise ValueError("Header and data shape disagree")
    if path.suffix == ".nii":
        expected_bytes = (
            int(getattr(image.dataobj, "offset", 0))
            + int(np.prod(image.shape)) * image.get_data_dtype().itemsize
        )
        if path.stat().st_size < expected_bytes:
            raise ValueError("Header shape/dtype exceed the available NIfTI file data")
    if image.ndim not in (3, 4) or (image.ndim == 4 and frame is None):
        raise ValueError("Select a frame explicitly for 4D anatomical input")
    if frame is not None and (image.ndim != 4 or not 0 <= frame < image.shape[3]):
        raise ValueError("Invalid selected 4D frame")
    unit, time_unit = header.get_xyzt_units()
    selected_unit = units_override or unit
    factors = {"meter": 1.0, "mm": 0.001, "micron": 1e-6}
    if selected_unit not in factors:
        raise ValueError(
            f"Unknown/unsupported spatial units {unit}; explicit units_override required"
        )
    factor = factors[selected_unit]
    q, qc = image.get_qform(coded=True)
    s, sc = image.get_sform(coded=True)
    q_raw, s_raw = image.get_qform(), image.get_sform()
    diagnostics = []
    if not qc and not sc:
        diagnostics.append("unspecified_spatial_transforms_nibabel_fallback")
    if qc and sc and not np.allclose(q * factor, s * factor, atol=1e-7, rtol=1e-5):
        diagnostics.append("conflicting_coded_qform_sform")
    if units_override:
        diagnostics.append("explicit_spatial_units_override")
    if policy not in ("error", "nibabel", "qform", "sform"):
        raise ValueError("Invalid NIfTI affine policy")
    if (
        diagnostics
        and policy == "error"
        and any(x != "explicit_spatial_units_override" for x in diagnostics)
    ):
        raise ValueError(
            f"Ambiguous NIfTI geometry: {diagnostics}; choose an explicit affine policy"
        )
    if policy == "qform":
        if not qc:
            raise ValueError("Requested qform is not coded")
        affine, selected = q, "explicit_qform"
    elif policy == "sform":
        if not sc:
            raise ValueError("Requested sform is not coded")
        affine, selected = s, "explicit_sform"
    else:
        affine = header.get_best_affine()
        selected = "sform" if sc else "qform" if qc else "nibabel_base_affine"
    if diagnostics:
        warnings.warn(
            "NIfTI spatial diagnostics: " + ", ".join(diagnostics), UserWarning, stacklevel=2
        )
    # Validate every coded form, not only the selected one.
    for coded in (q, s):
        if coded is not None:
            validate_affine(coded)
    a = np.array(affine, dtype=float)
    a[:3] *= factor
    pixdim = np.asarray(header.get_zooms()[:3]) * factor
    if not np.allclose(np.linalg.norm(a[:3, :3], axis=0), pixdim, atol=1e-7, rtol=1e-4):
        diagnostics.append("selected_affine_spacing_differs_from_pixdim")
    metadata = {
        "source_path": str(path.resolve()),
        "source_sha256": sha256(path),
        "nifti_class": type(image).__name__,
        "qform": None if q is None else q.tolist(),
        "qform_code": int(qc),
        "qform_stored_raw": q_raw.tolist(),
        "sform_stored_raw": s_raw.tolist(),
        "sform": None if s is None else s.tolist(),
        "sform_code": int(sc),
        "selected_affine_source": selected,
        "affine_policy": policy,
        "source_spatial_units": unit,
        "interpreted_spatial_units": selected_unit,
        "time_units": time_unit,
        "pixdim_m": pixdim.tolist(),
        "slope": float(getattr(image.dataobj, "slope", 1)),
        "intercept": float(getattr(image.dataobj, "inter", 0)),
        "diagnostics": diagnostics,
        "source_shape": list(image.shape),
        "selected_frame": frame,
        "lazy": True,
    }
    return Volume(
        image.dataobj if frame is None else _FrameProxy(image.dataobj, frame), a, kind, metadata
    )


def save_nifti(volume: Volume, path: Path, *, version: Literal[1, 2] = 1) -> None:
    """Write a new derived file; never overwrite an existing source or result."""
    if path.exists():
        raise FileExistsError(path)
    a = volume.affine_m.copy()
    a[:3] *= 1000
    if version not in (1, 2):
        raise ValueError("NIfTI output version must be 1 or 2")
    data = volume.array()
    if data.dtype.kind == "b":
        data = data.astype(np.uint8)  # NIfTI has no NiBabel-supported boolean storage dtype.
    image_class: Any = nib.Nifti1Image if version == 1 else nib.Nifti2Image
    image = image_class(data, a, dtype=data.dtype)
    image.header.set_xyzt_units("mm")
    image.set_sform(a, code=2)
    # qform cannot represent shear: mark it uncoded rather than approximating it.
    direction = a[:3, :3] / np.linalg.norm(a[:3, :3], axis=0)
    if np.allclose(direction.T @ direction, np.eye(3), atol=1e-7):
        image.set_qform(a, code=2)
    else:
        image.set_qform(None, code=0)
    nib.save(image, path)
