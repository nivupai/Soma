"""MRI geometry in RAS+ metres; scoring never registers or resamples implicitly."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from soma.benchmarks.segmentation import LabelVolume as LabelVolume
from soma.benchmarks.segmentation import score as _score
from soma.geometry import Frame as Frame
from soma.geometry import Points as Points
from soma.geometry import Transform as Transform
from soma.geometry.coordinates import ras_lps as ras_lps
from soma.imaging.mesh_quality import mesh_quality as mesh_quality
from soma.imaging.nifti import load_nifti as load_nifti
from soma.imaging.nifti import save_nifti as save_nifti
from soma.imaging.registration import RegistrationConfig as RegistrationConfig
from soma.imaging.registration import RegistrationResult as RegistrationResult
from soma.imaging.registration import register as register
from soma.imaging.resampling import resample as resample
from soma.imaging.surfaces import Mesh as Mesh
from soma.imaging.surfaces import extract_surface as extract_surface
from soma.imaging.validation import validate_volume as validate_volume
from soma.imaging.volumes import Volume as Volume


def require_same_space(left: Volume, right: Volume, *, subject: str, space: str) -> None:
    """Require declared matching identity and voxel grids; shape alone is insufficient.

    Both volume.metadata dictionaries must explicitly contain subject and space.
    Coordinate geometry remains RAS+ metres; this does not certify coregistration.
    """
    if not subject or not space:
        raise ValueError("Explicit subject and space required")
    for volume in (left, right):
        if volume.metadata.get("subject") != subject or volume.metadata.get("space") != space:
            raise ValueError("Missing or mismatched subject/space metadata")
    if not left.same_grid(right):
        raise ValueError("Voxel grids differ; explicit justified resampling required")


def resample_labels(source: Volume, reference: Volume, *, reference_to_source: Transform) -> Volume:
    """Explicit reference-to-source RAS metre pull mapping; nearest labels only."""
    if source.kind != "labels":
        raise ValueError("Discrete label volume required")
    return resample(source, reference, reference_to_source=reference_to_source, order=0)


def inspect_volumes(paths: Iterable[Path]) -> list[dict[str, Any]]:
    """Strict lazy NIfTI inspection in input order; stop on the first invalid input."""
    return [validate_volume(load_nifti(path)) for path in paths]


def score(
    prediction: LabelVolume,
    reference: LabelVolume,
    *,
    tolerances_mm: tuple[float, ...] = (1.0, 2.0),
    valid_mask: Volume | None = None,
) -> dict[str, Any]:
    """Existing physical surfel metrics, additionally rejecting undeclared label IDs.

    0 is background. Reference and prediction must have identical explicit
    subject, space, ontology and grid. No implicit registration or resampling.
    """
    for item in (prediction, reference):
        if not set(np.unique(item.volume.array())).issubset({0, *item.ontology}):
            raise ValueError("Unknown segmentation label outside declared ontology")
    return _score(prediction, reference, tolerances_mm=tolerances_mm, valid_mask=valid_mask)
