"""Core-only analytical physical contract; full BEM study is explicitly opt-in."""

import numpy as np

from soma.sdk.source import bem_diagnostic_design, bem_diagnostic_protocol
from soma.source.bem_discrepancy import field_metrics, homogeneous_series, sensors


def run():
    ss = sensors(None)
    g = homogeneous_series(np.zeros((1, 3)), ss)
    exact = 3 * ss / (4 * np.pi * 0.33 * 0.09**3)
    assert np.allclose(g, exact, rtol=1e-13, atol=1e-12)
    assert field_metrics(g, exact)["relative"] < 1e-12
    return dict(
        synthetic_only=True,
        human_subjects=0,
        analytical_central_error=field_metrics(g, exact)["relative"],
        protocol=bem_diagnostic_protocol().protocol.fingerprint,
        target=bem_diagnostic_design()["thresholds"]["independent_agreement"],
    )
