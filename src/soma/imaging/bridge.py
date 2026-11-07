"""MRI-to-source boundary: explicit subject identity and justified transform chains."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from soma.geometry import Frame, Transform
from soma.imaging.mesh_quality import nested_boundaries
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume


@dataclass(frozen=True)
class AnatomicalModel:
    subject: str
    volume: Volume
    boundaries: tuple[Mesh, Mesh, Mesh]
    ras_to_mne_mri: Transform
    transform_provenance: str

    def __post_init__(self) -> None:
        if (
            not self.subject
            or not self.transform_provenance
            or not self.volume.metadata.get("origin", self.volume.metadata.get("source_sha256"))
        ):
            raise ValueError(
                "Subject, MRI provenance and explicit RAS-to-MNE justification required"
            )
        if (
            self.ras_to_mne_mri.source != Frame.RAS
            or self.ras_to_mne_mri.destination != Frame.MRI
            or not self.ras_to_mne_mri.rigid
        ):
            raise ValueError("Require a validated rigid RAS-to-participant-MNE-MRI transform")
        if any(mesh.vertices.frame != Frame.RAS for mesh in self.boundaries):
            raise ValueError("Boundaries must be in the MRI volume's RAS metre frame")

    def validate_sensor_alignment(
        self, *, subject: str, head_to_mri: Transform, provenance: str
    ) -> dict[str, Any]:
        if (
            subject != self.subject
            or not provenance
            or not head_to_mri.rigid
            or head_to_mri.source != Frame.HEAD
            or head_to_mri.destination != Frame.MRI
        ):
            raise ValueError(
                "EEG subject identity and justified rigid head-to-MRI coregistration required"
            )

        chain = head_to_mri.then(self.ras_to_mne_mri.inverse())
        return {
            "subject": self.subject,
            "alignment_provenance": provenance,
            "head_to_MNE_MRI_m": head_to_mri.matrix.tolist(),
            "head_to_NIfTI_RAS_m": chain.matrix.tolist(),
            "units": "m",
            "anatomical_accuracy_validated": False,
        }

    def mne_candidates(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        diagnostics = nested_boundaries(list(self.boundaries))
        if not diagnostics["geometric_candidate"]:
            raise ValueError("Candidate surfaces fail geometric readiness checks")
        candidates = []
        for identity, mesh in zip((1, 3, 4), self.boundaries, strict=True):
            rr = self.ras_to_mne_mri.apply(mesh.vertices).xyz
            candidates.append(
                {"id": identity, "rr": rr, "tris": np.array(mesh.faces), "coord_frame": 5}
            )
        diagnostics.update(
            {
                "subject": self.subject,
                "frame": "MNE MRI",
                "units": "m",
                "MRI_grid": self.volume.grid_id,
                "MRI_provenance": self.volume.metadata,
                "MRI_geometry": self.volume.geometry(),
                "NIfTI_RAS_to_MNE_MRI_m": self.ras_to_mne_mri.matrix.tolist(),
                "transform_provenance": self.transform_provenance,
                "coregistration_provided": False,
                "individual_forward_validated": False,
            }
        )
        return candidates, diagnostics
