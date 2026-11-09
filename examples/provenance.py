"""Roundtrip existing manifest plus explicit SDK semantics; no private paths."""

import json
import tempfile
from pathlib import Path

import numpy as np

from soma.sdk.provenance import (
    array_fingerprint,
    read_manifest,
    require_comparable,
    result_metadata,
    write_json,
)


def run():
    result = result_metadata(
        input_fingerprint=array_fingerprint(np.arange(5.0)),
        method="synthetic-summary-v1",
        parameters={"operation": "identity"},
        units="dimensionless",
        data_identity="synthetic-seed-16042",
        estimand="sample vector",
        spatial_reference=None,
        interpretation="synthetic",
        warnings=[],
        source={"generator": "arange", "synthetic": True},
        seed=16042,
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        write_json(path, result)
        loaded = read_manifest(path)
    require_comparable(result, loaded)
    return {
        k: result[k]
        for k in [
            "application_version",
            "input_fingerprint",
            "method",
            "units",
            "interpretation",
            "confirmatory_claim_allowed",
        ]
    }


if __name__ == "__main__":
    print(json.dumps(run(), allow_nan=False))
