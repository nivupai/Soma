"""Deterministic demonstrations only; never a substitute for anatomical validation."""

from soma.experiments.fmri_simulation import simulate as simulate_fmri
from soma.imaging.phantoms import asymmetric as asymmetric
from soma.imaging.phantoms import ellipsoid as ellipsoid
from soma.signal.synthetic import synthetic as synthetic_signal

__all__ = ["simulate_fmri", "asymmetric", "ellipsoid", "synthetic_signal"]
