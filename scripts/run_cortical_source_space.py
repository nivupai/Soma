"""Cortical midsurface source space on a local FreeSurfer subject; public aggregates only.

The public JSON carries counts, fractions, exclusions and implementation hashes; it
never carries MRI-derived fingerprints, coordinates or paths. ``--private-dir`` keeps
the source arrays, identity and input file hashes locally (never commit it).
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import mne
import numpy as np

from soma.anatomy.surfaces import ConductorSurfaces
from soma.core.provenance import sha256, write_json
from soma.source.cortical import HemisphereSurfaces, build_cortical_source_space

IMPLEMENTATION = ["scripts/run_cortical_source_space.py", "src/soma/source/cortical.py"]
BASELINE = Path("experiments/milestone32/aggregate.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--subjects-dir", type=Path, default=Path("data/raw/mne-sample/MNE-sample-data/subjects")
    )
    parser.add_argument("--subject", default="sample")
    parser.add_argument("--bem", default="bem/sample-5120-5120-5120-bem.fif")
    parser.add_argument("--spacing", default="oct6")
    parser.add_argument("--minimum-margin-mm", type=float, default=0.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    subject_dir = args.subjects_dir / args.subject
    hemispheres = [HemisphereSurfaces.from_freesurfer(subject_dir, h) for h in ("lh", "rh")]
    bem_path = subject_dir / args.bem
    conductor = ConductorSurfaces.from_mne(
        args.subject,
        mne.read_bem_surfaces(bem_path, verbose=False),
        {"source": "subject BEM surfaces (inner skull used for containment)"},
    )
    space = build_cortical_source_space(
        hemispheres,
        conductor.meshes[0],
        spacing=args.spacing,
        minimum_margin_m=args.minimum_margin_mm * 1e-3,
    )
    public = dict(space.report)
    baseline = json.loads(BASELINE.read_text())["source_coverage"]
    public["volumetric_baseline"] = {
        "source": str(BASELINE),
        "eligible_fraction": baseline["eligible_fraction"],
        "definition": baseline["definition"],
        "comparable_measure": False,
        "note": "voxel-count fraction of GM inside an inscribed region vs. surface-area "
        "fraction; reported side by side, not as the same estimand",
    }
    public["subject"] = "MNE sample (public dataset)" if args.subject == "sample" else "local"
    public["implementation_sha256"] = {
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in IMPLEMENTATION
    }
    public["seconds"] = time.perf_counter() - start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, public)
    if args.private_dir is not None:
        args.private_dir.mkdir(parents=True, exist_ok=False)
        inputs = [subject_dir / f"surf/{h}.{s}" for h in ("lh", "rh") for s in ("white", "pial")]
        inputs += [subject_dir / f"label/{h}.aparc.annot" for h in ("lh", "rh")] + [bem_path]
        write_json(
            args.private_dir / "receipt.private.json",
            {
                "identity_sha256": space.identity,
                "inputs_sha256": {str(p): sha256(p) for p in inputs},
            },
        )
        np.savez_compressed(
            args.private_dir / "sources.npz",
            positions_m=space.positions_m,
            normals=space.normals,
            areas_m2=space.areas_m2,
            source_ids=np.array(space.source_ids),
        )
    coverage = public["coverage"]
    print(
        f"{space.positions_m.shape[0]} sources; area coverage "
        f"{coverage['area_fraction_of_midsurface']:.4f} of midsurface"
    )


if __name__ == "__main__":
    main()
