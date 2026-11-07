"""Frame-safe geometry, independent of a particular EEG dataset or renderer."""

from soma.geometry.electrodes import Electrodes
from soma.geometry.frames import Frame, Points, SourceCoordinates
from soma.geometry.transforms import Transform

__all__ = ["Electrodes", "Frame", "Points", "SourceCoordinates", "Transform"]
