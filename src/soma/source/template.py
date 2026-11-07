"""Explicit fsaverage assets; ordinary reads and tests never fetch resources."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.core.provenance import sha256
from soma.geometry import Electrodes, Frame, Points, Transform
from soma.simulations.calibration import atomic_json


@dataclass(frozen=True)
class Template:
    subjects_dir: Path = Path("data/anatomy")
    name: str = "fsaverage"

    @property
    def root(self) -> Path:
        return self.subjects_dir / self.name

    @property
    def bem(self) -> Path:
        return self.root / "bem/fsaverage-5120-5120-5120-bem-sol.fif"

    @property
    def trans_path(self) -> Path:
        return self.root / "bem/fsaverage-trans.fif"

    @property
    def transform(self) -> Transform:
        return Transform.from_mne(mne.read_trans(self.trans_path, verbose=False), template=True)

    def files(self) -> list[Path]:
        return [
            self.bem,
            self.trans_path,
            self.root / "surf/lh.white",
            self.root / "surf/rh.white",
            self.root / "bem/outer_skin.surf",
        ]

    def inspect(self) -> dict[str, Any]:
        missing = [str(p) for p in self.files() if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                f"Missing template assets {missing}; "
                "explicitly run soma source inspect-template --fetch"
            )
        return {
            "template": self.name,
            "subjects_dir": str(self.subjects_dir.resolve()),
            "resource_version": "MNE fsaverage OSF root v2 / BEM v4; identity by file SHA256",
            "mne_version": mne.__version__,
            "assets": {str(p.relative_to(self.subjects_dir)): sha256(p) for p in self.files()},
            "head_to_template_mri": self.transform.matrix.tolist(),
            "anatomy": "template, not participant anatomy",
            "conductivity_S_per_m": [
                float(s["sigma"]) for s in mne.read_bem_solution(self.bem, verbose=False)["surfs"]
            ],
        }

    def fetch(self) -> dict[str, Any]:
        if self.name != "fsaverage":
            raise ValueError("Only explicit fsaverage fetching is supported")
        self.subjects_dir.mkdir(parents=True, exist_ok=True)
        previous = os.environ.get("SUBJECTS_DIR")
        os.environ["SUBJECTS_DIR"] = str(self.subjects_dir.resolve())
        try:
            mne.datasets.fetch_fsaverage(subjects_dir=str(self.subjects_dir.resolve()))
        finally:
            if previous is None:
                os.environ.pop("SUBJECTS_DIR", None)
            else:
                os.environ["SUBJECTS_DIR"] = previous
        return self.inspect()

    def source_space(self, spacing: str = "ico3") -> Any:
        anatomy = self.inspect()
        path = self.root / "bem" / f"soma-{spacing}-white-src.fif"
        receipt = path.with_suffix(".json")
        identity = {
            "assets": anatomy["assets"],
            "spacing": spacing,
            "surface": "white",
            "mne": mne.__version__,
        }
        if path.exists():
            if not receipt.exists() or json.loads(receipt.read_text()) != {
                "identity": identity,
                "sha256": sha256(path),
            }:
                raise ValueError("Source-space cache identity mismatch; use a fresh template cache")
            return mne.read_source_spaces(path, verbose=False)
        src = mne.setup_source_space(
            self.name,
            spacing=spacing,
            surface="white",
            subjects_dir=self.subjects_dir,
            add_dist=False,
            n_jobs=1,
            verbose=False,
        )
        with tempfile.TemporaryDirectory(dir=path.parent, prefix=".soma-src-") as staging:
            temporary = Path(staging) / "white-src.fif"
            mne.write_source_spaces(temporary, src, overwrite=False, verbose=False)
            os.replace(temporary, path)
        atomic_json(receipt, {"identity": identity, "sha256": sha256(path)})
        return src

    def scalp_head(self) -> Points:
        scalp_mm, _ = mne.read_surface(self.root / "bem/outer_skin.surf", verbose=False)
        return self.transform.inverse().apply(Points.from_mm(scalp_mm, Frame.TEMPLATE_MRI))

    def sensor_info(self, names: list[str], sfreq: float = 160) -> tuple[Any, dict[str, Any]]:
        self.inspect()
        info = mne.create_info(names, sfreq, "eeg")
        montage = mne.channels.make_standard_montage("fsaverage_1005")
        info.set_montage(montage, match_case=True, on_missing="raise")
        raw = mne.io.RawArray(np.zeros((len(names), 2)), info, verbose=False)
        raw.set_eeg_reference("average", projection=True, verbose=False)
        info = raw.info
        xyz = np.array([ch["loc"][:3] for ch in info["chs"]])
        electrodes = Electrodes(tuple(names), Points(xyz, Frame.HEAD))
        electrodes.require_head()
        scalp = self.scalp_head()
        geometry = electrodes.scalp_diagnostics(scalp)
        if geometry["max_distance_m"] > 0.025:  # type: ignore[operator]
            raise ValueError("Template montage is implausibly far from template scalp")
        # Quantify fiducial-derived montage vs supported fsaverage transform agreement.
        # The documented MNE pair differs slightly; this is not exact registration.
        positions = montage.get_positions()
        original = np.array([positions["ch_pos"][name] for name in names])
        transformed = self.transform.inverse().apply(Points(original, Frame.TEMPLATE_MRI)).xyz
        error = float(np.max(np.abs(transformed - xyz)))
        if error > 0.005:
            raise ValueError("Montage and fsaverage transform do not correspond")
        geometry.update(
            {
                "montage": "fsaverage_1005",
                "montage_native_vs_supported_trans_max_m": error,
                "sensor_count": len(names),
                "digitization": "template_not_individual",
            }
        )
        return info, geometry
