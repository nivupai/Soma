"""Participant-matched MNE sample assets; explicit fetching and identity receipts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mne
import nibabel as nib
import numpy as np

from soma.core.provenance import sha256
from soma.geometry import Frame, Points, Transform


@dataclass(frozen=True)
class SampleAssets:
    root: Path = Path("data/raw/mne-sample")
    subject: str = "sample"

    @property
    def data(self) -> Path:
        return self.root / "MNE-sample-data"

    @property
    def subjects_dir(self) -> Path:
        return self.data / "subjects"

    @property
    def subject_dir(self) -> Path:
        return self.subjects_dir / self.subject

    @property
    def raw_path(self) -> Path:
        return self.data / "MEG/sample/sample_audvis_filt-0-40_raw.fif"

    @property
    def transform_path(self) -> Path:
        return self.data / "MEG/sample/sample_audvis_raw-trans.fif"

    @property
    def transform(self) -> Transform:
        return Transform.from_mne(mne.read_trans(self.transform_path, verbose=False))

    def fetch(self) -> Path:
        if self.subject != "sample":
            raise ValueError("MNE sample recordings are not matched to morph/fsaverage")
        self.root.mkdir(parents=True, exist_ok=True)
        return Path(
            mne.datasets.sample.data_path(
                path=self.root.resolve(), update_path=False, download=True
            )
        )

    def required_files(self) -> list[Path]:
        return [
            self.raw_path,
            self.transform_path,
            self.subject_dir / "mri/T1.mgz",
            self.subject_dir / "mri/transforms/talairach.xfm",
            self.subject_dir / "bem/sample-oct-6-src.fif",
        ] + [
            self.subject_dir / p
            for p in [
                "bem/inner_skull.surf",
                "bem/outer_skull.surf",
                "bem/outer_skin.surf",
                "surf/lh.white",
                "surf/rh.white",
            ]
        ]

    def inspect(self, modality: str = "eeg") -> dict[str, Any]:
        if modality not in ("eeg", "meg"):
            raise ValueError("Select EEG or separately labeled MEG")
        if self.subject != "sample":
            raise ValueError(
                "Participant mismatch: sample electrophysiology requires sample anatomy"
            )
        missing = [str(p) for p in self.required_files() if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                f"Missing matched sample assets {missing}; explicitly fetch the dataset"
            )
        source = mne.read_source_spaces(
            self.subject_dir / "bem/sample-oct-6-src.fif", verbose=False
        )
        if any(s.get("subject_his_id") != "sample" for s in source):
            raise ValueError("Source-space participant identity mismatch")
        raw = mne.io.read_raw_fif(self.raw_path, preload=False, verbose=False)
        try:
            dig = raw.info["dig"] or []
            counts = {
                name: sum(int(d["kind"]) == kind for d in dig)
                for name, kind in [("cardinal", 1), ("HPI", 2), ("EEG", 3), ("headshape_EXTRA", 4)]
            }
            if any(int(d["coord_frame"]) != 4 for d in dig):
                raise ValueError("Sample digitization must be in head coordinates")
            picks = mne.pick_types(raw.info, meg=False, eeg=True, exclude="bads")
            locations = np.array([raw.info["chs"][i]["loc"][:3] for i in picks])
            if modality == "eeg" and (
                len(picks) < 3
                or not np.isfinite(locations).all()
                or np.any(np.linalg.norm(locations, axis=1) < 0.01)
            ):
                raise ValueError(
                    "Inadequate measured EEG geometry; do not invent template electrodes"
                )
            electrode_dig = {int(d["ident"]): d["r"] for d in dig if int(d["kind"]) == 3}
            comparisons = [
                float(
                    np.linalg.norm(
                        raw.info["chs"][i]["loc"][:3]
                        - electrode_dig[int(raw.ch_names[i].split()[-1])]
                    )
                )
                for i in picks
                if int(raw.ch_names[i].split()[-1]) in electrode_dig
            ]
            correspondence = max(comparisons) if comparisons else None
            if modality == ("eeg") and (
                len(comparisons) != len(picks)
                or correspondence is None
                or not np.isfinite(correspondence)
                or correspondence > 1e-6
            ):
                raise ValueError(
                    "Retained EEG labels/locations do not match digitized EEG point identities"
                )
            cardinal = [d for d in dig if int(d["kind"]) == 1]
            if {int(d["ident"]) for d in cardinal} != {1, 2, 3}:
                raise ValueError("Missing/misidentified head fiducials")
            image: Any = nib.load(self.subject_dir / "mri/T1.mgz")
            native_inspection = {}
            for name in ("inner_skull", "outer_skull", "outer_skin"):
                rr, tris = mne.read_surface(
                    self.subject_dir / "bem" / (name + ".surf"), verbose=False
                )
                native_inspection[name] = {
                    "vertex_count": len(rr),
                    "face_count": len(tris),
                    "finite_vertices": bool(np.isfinite(rr).all()),
                    "coordinate_units_on_disk": "mm",
                    "frame": "FreeSurfer MRI surface RAS",
                    "scope": "inventory only; full geometry QC applies to solver ico3 surfaces",
                }
            return {
                "MRI_geometry": {
                    "shape": [int(v) for v in image.shape],
                    "voxel_size_mm": [float(v) for v in image.header.get_zooms()],
                    "voxel_to_scanner_RAS_mm": image.affine.tolist(),
                    "voxel_to_MNE_MRI_mm": image.header.get_vox2ras_tkr().tolist(),
                    "MNE_MRI_units_in_models": "m",
                },
                "native_surface_inspection": native_inspection,
                "dataset": "mne-sample",
                "subject": self.subject,
                "mode": "participant_matched",
                "identity_evidence": (
                    "official curated matching MEG/sample and subjects/sample; "
                    "distributed source subject_his_id=sample"
                ),
                "raw_subject_info": raw.info["subject_info"],
                "identity_limitation": (
                    "recording subject_info absent; not independently authenticated identity"
                ),
                "source_URL": "https://osf.io/download/86qa2?version=6",
                "archive_MD5": "e8f30c4516abdc12a0c08e6bae57409c",
                "version": (self.data / "version.txt").read_text().strip(),
                "license_scope": (
                    "official MNE sample educational/tutorial data; not "
                    "hardware/MRI system performance evaluation"
                ),
                "license_source": "https://mne.tools/stable/documentation/datasets.html#sample",
                "assets_sha256": {
                    str(p.relative_to(self.data)): sha256(p) for p in self.required_files()
                },
                "digitization_counts": counts,
                "EEG_total": len(mne.pick_types(raw.info, meg=False, eeg=True, exclude=[])),
                "EEG_retained": len(picks),
                "EEG_digitization_correspondence_max_m": correspondence,
                "EEG_names": [raw.ch_names[i] for i in picks],
                "bad_channels": raw.info["bads"],
                "surface_origin": "FLASH-derived participant surfaces via default symlinks",
                "surface_products": {
                    name: {
                        "resolved_path": str(
                            (self.subject_dir / "bem" / (name + ".surf")).resolve()
                        ),
                        "default_equals_FLASH": sha256(self.subject_dir / "bem" / (name + ".surf"))
                        == sha256(self.subject_dir / "bem/flash" / (name + ".surf")),
                    }
                    for name in ("inner_skull", "outer_skull", "outer_skin")
                },
                "MRI_fiducial_file_present": False,
                "MRI_fiducial_comparison": (
                    "MNI-derived initialization estimate only, no manually "
                    "digitized MRI fiducial truth"
                ),
                "head_to_MRI_m": self.transform.matrix.tolist(),
                "available_modalities": ["EEG", "MEG", "structural MRI"],
                "used_modality": modality.upper(),
            }
        finally:
            raw.close()

    def eeg_info(self) -> Any:
        self.inspect()
        raw = mne.io.read_raw_fif(self.raw_path, preload=False, verbose=False)
        raw.pick("eeg", exclude="bads")
        raw.del_proj()
        raw.set_eeg_reference("average", projection=True, verbose=False)
        info = raw.info.copy()
        raw.close()
        return info

    def digitized(self, kind: int) -> Points:
        info = mne.io.read_info(self.raw_path, verbose=False)
        return Points(np.array([d["r"] for d in info["dig"] if int(d["kind"]) == kind]), Frame.HEAD)

    def fiducials(self) -> tuple[Points, Points, dict[str, Any]]:
        info = mne.io.read_info(self.raw_path, verbose=False)
        head = {int(d["ident"]): d["r"] for d in info["dig"] if int(d["kind"]) == 1}
        derived = mne.coreg.get_mni_fiducials(
            self.subject, subjects_dir=self.subjects_dir, verbose=False
        )
        target = {int(d["ident"]): d["r"] for d in derived}
        return (
            Points(np.array([head[k] for k in (1, 2, 3)]), Frame.HEAD),
            Points(np.array([target[k] for k in (1, 2, 3)]), Frame.MRI),
            {
                "names": ["LPA", "nasion", "RPA"],
                "MRI_fiducials_origin": (
                    "MNE get_mni_fiducials, derived via participant talairach; "
                    "not manual anatomical truth"
                ),
            },
        )
