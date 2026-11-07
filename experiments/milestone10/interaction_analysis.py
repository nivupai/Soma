"""Supplemental contrasts of prespecified levels; no additional model selection."""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from soma.core.provenance import sha256
from soma.reliability.workflows import paired_interval


def analyze(report: Path, output: Path) -> dict[str, Any]:
    """BEM-minus-analytical difference at high lambda minus that at low lambda.

    Includes every source/angle/representation/grid group in the fixed design.
    This contrasts numerical conductor discretization and regularization, not
    biological anatomical variability. Shared analytical approximations remain.
    """
    records = []
    with np.load(report / "source-arrays.npz", allow_pickle=False) as data:
        for source in range(3):
            for angle in (0, 30):
                for spacing in (0.02, 0.015, 0.01):
                    for representation in ("fixed", "free"):
                        for metric in ("peak_mm", "nearest_ratio"):
                            keys = {
                                (kind, regularization): (
                                    f"{source}:{angle}:{spacing}:{kind}:{representation}:"
                                    f"{regularization}:baseline:SNR10:{metric}"
                                )
                                for kind in ("BEM", "analytical")
                                for regularization in (1.0, 0.01)
                            }
                            contrast = (
                                data[keys["BEM", 1.0]]
                                - data[keys["analytical", 1.0]]
                                - data[keys["BEM", 0.01]]
                                + data[keys["analytical", 0.01]]
                            )
                            if contrast.shape != (20,):
                                raise ValueError("Expected 20 paired noise realizations")
                            records.append(
                                {
                                    "source": source,
                                    "angle_deg": angle,
                                    "spacing_m": spacing,
                                    "representation": representation,
                                    "metric": metric,
                                    "contrast": paired_interval(contrast),
                                }
                            )
    result = {
        "scope": "supplemental all-group contrast from prespecified parameter levels",
        "definition": "(BEM-analytical at lambda2=1) - (BEM-analytical at lambda2=.01)",
        "biological_variance_decomposition": False,
        "source_arrays_sha256": sha256(report / "source-arrays.npz"),
        "analysis_code_sha256": sha256(Path(__file__)),
        "records": records,
    }
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


if __name__ == "__main__":
    analyze(Path(sys.argv[1]), Path(sys.argv[2]))
