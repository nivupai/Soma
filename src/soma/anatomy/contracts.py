"""A subject-specific model is a different mode from a template model."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from soma.anatomy.surfaces import ConductorSurfaces
from soma.geometry import Electrodes, Frame, Points, Transform


def validate_eeg_info(info: Any) -> list[dict[str, Any]]:
    names = info["ch_names"]
    if info["bads"]:
        raise ValueError("Individual EEG info must explicitly exclude marked bad channels")
    Electrodes(tuple(names), Points(np.array([ch["loc"][:3] for ch in info["chs"]]), Frame.HEAD))
    if any(
        int(ch["kind"]) != 2 or int(ch["unit"]) != 107 or int(ch["coord_frame"]) != 4
        for ch in info["chs"]
    ):
        raise ValueError("Individual EEG channels require EEG type, volts and head coordinates")
    if not np.isfinite(np.array([ch["loc"][:6] for ch in info["chs"]])).all():
        raise ValueError("Electrode/reference integration positions must be finite")
    projections = info["projs"]
    if len(projections) != 1:
        raise ValueError("Individual EEG requires exactly the retained-channel average projector")
    data = projections[0]["data"]
    vector = np.asarray(data["data"])
    if (
        data["col_names"] != names
        or vector.shape != (1, len(names))
        or not np.isfinite(vector).all()
        or vector[0, 0] == 0
        or not np.allclose(vector, vector[0, 0])
    ):
        raise ValueError("EEG projector/channel correspondence is not a common average")
    return [
        {
            "description": projections[0]["desc"],
            "active": bool(projections[0]["active"]),
            "channels": names,
            "data": vector.tolist(),
        }
    ]


@dataclass(frozen=True)
class IndividualModel:
    subject: str
    sensor_subject: str
    source_subject: str
    surfaces: ConductorSurfaces
    info: Any
    head_to_mri: Transform
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        if (
            not self.subject
            or len({self.subject, self.sensor_subject, self.source_subject, self.surfaces.subject})
            != 1
        ):
            raise ValueError(
                "Participant identity mismatch between anatomy, source space and sensors"
            )
        if self.subject in ("fsaverage", "template"):
            raise ValueError("A template is not a participant-matched model")
        if (
            self.head_to_mri.source != Frame.HEAD
            or self.head_to_mri.destination != Frame.MRI
            or not self.head_to_mri.rigid
        ):
            raise ValueError("Require a rigid participant head-to-MRI transform")
        if self.provenance.get("sensor_origin") != "digitized_EEG":
            raise ValueError(
                "Individual EEG requires measured digitization, not "
                "template/headshape/HPI substitution"
            )
        validate_eeg_info(self.info)
        names = self.info["ch_names"]
        if len(names) != len(set(names)) or len(names) < 3:
            raise ValueError("Unique retained electrode identities required")
        xyz = np.array([ch["loc"][:3] for ch in self.info["chs"]])
        if any(int(ch["coord_frame"]) != 4 for ch in self.info["chs"]):
            raise ValueError("EEG sensors must use head coordinates")
        Electrodes(tuple(names), Points(xyz, Frame.HEAD))
        if not np.isfinite(xyz).all() or np.any(np.linalg.norm(xyz, axis=1) < 0.01):
            raise ValueError("Inadequate electrode positions")

    def receipt(self) -> dict[str, Any]:
        return {
            "mode": "participant_matched",
            "subject": self.subject,
            "sensor_subject": self.sensor_subject,
            "source_subject": self.source_subject,
            "channels": self.info["ch_names"],
            "projector_state": validate_eeg_info(self.info),
            "head_to_MRI_m": self.head_to_mri.matrix.tolist(),
            "sensor_positions_head_m": [ch["loc"][:3].tolist() for ch in self.info["chs"]],
            "provenance": self.provenance,
            "coordinate_frame": "head/MRI metres",
            "transform_uncertainty": "sensitivity only; not calibrated anatomical posterior",
        }
