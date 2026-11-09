"""Explicitly scoped inference; nominal feasible-AR maps are not confirmation."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import false_discovery_control


def adjust_probabilities(p: np.ndarray[Any, Any], method: str = "bh") -> np.ndarray[Any, Any]:
    p = np.asarray(p, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("Finite nonempty one-dimensional probabilities in[0,1] required")
    if method in {"bh", "by"}:
        return np.asarray(false_discovery_control(p, method=method))
    if method == "bonferroni":
        return np.asarray(np.minimum(1.0, len(p) * p))
    raise ValueError("Unsupported multiple-comparison procedure")


@dataclass(frozen=True)
class InferencePolicy:
    mode: str = "descriptive"
    correction: str = "bh"

    def evaluate(self, run: Any, config: Any, design: Any) -> dict[str, Any]:
        if self.mode not in {"descriptive", "confirmatory"} or self.correction not in {
            "bh",
            "by",
            "bonferroni",
        }:
            raise ValueError("Unsupported statistical policy")
        approved = False
        if self.mode == "confirmatory":
            contract = run.provenance.get("calibration_contract", {})
            approved = (
                run.preprocessing == "synthetic"
                and config.noise_model == "ols"
                and config.smoothing_fwhm == 0
                and run.n_scans == 100
                and int(run.mask.array().sum()) in {1, 27, 343}
                and config.q == 0.05
                and self.correction == "bh"
                and contract.get("family") == "iid-Gaussian-fixed-X-independent-voxels"
                and list(design.columns) == ["task", "motion", "trend", "constant"]
            )
            if not approved:
                raise ValueError(
                    "Unsupported confirmatory inference; use descriptive feasible-AR/human maps"
                )
        return {
            "mode": self.mode,
            "correction": self.correction,
            "confirmatory_claim_allowed": approved,
            "status": "conditionally supported synthetic iid-OLS class"
            if approved
            else "experimental nominal tests; descriptive effects retained",
            "scope": "synthetic iid Gaussian OLS, fixed X/mask; tested n100/families only",
            "assumptions_verified_from_data": False,
            "declaration_source": "explicit synthetic contract, not a noise classifier",
        }
