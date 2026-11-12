"""Export only the verified synthetic M26 tables and vector figures; no human inputs."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from soma.experiments.source_uncertainty import read_uncertainty
from soma.source.uncertainty import scenarios


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("figures", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    report = read_uncertainty(a.root / "manifest/result.json")
    for name, expected in report["files"].items():
        path = a.root / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Changed or unsafe numerical table")
    a.output.mkdir(parents=True, exist_ok=False)
    for path in a.root.iterdir():
        if path.is_file() and path.suffix in [".csv", ".json"]:
            shutil.copyfile(path, a.output / path.name)
    shutil.copytree(a.root / "manifest", a.output / "manifest")
    (a.output / "figures").mkdir()
    for path in a.figures.iterdir():
        if path.suffix in [".svg", ".csv"]:
            target = a.output / "figures" / path.name
            if path.suffix == ".svg":
                target.write_text(
                    "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
                )
            else:
                shutil.copyfile(path, target)
    g = pd.read_csv(
        a.root / "truth-leadfield_V_per_Am.csv", float_precision="round_trip"
    ).to_numpy()
    moments = pd.read_csv(a.root / "truth-moments.csv", float_precision="round_trip").to_numpy()
    y = pd.read_csv(a.root / "measurements_V.csv", float_precision="round_trip").to_numpy()
    index = pd.read_csv(a.root / "measurement-index.csv")
    noise = []
    for j, row in enumerate(index.itertuples()):
        clean = g[:, 3 * row.source : 3 * row.source + 3] @ moments[row.source]
        snr = (
            None
            if row.noise_std_V == 0
            else float(20 * np.log10(np.linalg.norm(clean) / np.linalg.norm(y[:, j] - clean)))
        )
        noise.append(
            {
                "source": row.source,
                "std_V": row.noise_std_V,
                "draw": row.draw,
                "realized_SNR_dB": snr,
            }
        )
    pd.DataFrame(noise).to_csv(a.output / "noise-diagnostics.csv", index=False)
    physical = {
        tuple(
            s[k]
            for k in [
                "inner_mm",
                "outer_mm",
                "skull",
                "electrode_mm",
                "pattern",
                "translation_mm",
                "rotation_deg",
            ]
        )
        for s in scenarios()
    }
    receipt = {
        "schema": "soma.source-uncertainty.public-evidence/1",
        "synthetic_only": True,
        "human_subjects": 0,
        "planned_configuration_rows": 49,
        "distinct_physical_settings": len(physical),
        "independent_generators": 12,
        "distinct_measurement_vectors": 204,
        "computed_rows": report["case_rows"] - report["failed_rows"],
        "failed_rows": report["failed_rows"],
        "not_human_population_uncertainty": True,
        "files": {
            str(p.relative_to(a.output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(a.output.rglob("*"))
            if p.is_file()
        },
    }
    (a.output / "evidence.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
