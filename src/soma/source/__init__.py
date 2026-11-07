"""Frame-safe anatomical MNE modeling and independent numerical validation."""

from soma.source.inverse import CorticalInverse, Tikhonov
from soma.source.noise import NoiseModel
from soma.source.resolution import Resolution

__all__ = ["CorticalInverse", "NoiseModel", "Resolution", "Tikhonov"]
