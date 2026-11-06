"""Geometry boundary: template positions explicitly distinguished from digitization."""

from typing import Any

import mne
import numpy as np

from soma.eeg.preprocessing import select_eeg


def assign_geometry(
    raw: Any,
    montage: Any | None = None,
    *,
    provenance: str = "MNE 1005 template; not measured",
) -> tuple[Any, dict[str, Any]]:
    """Return a copy and finite positions in MNE head coordinates (meters).

    Future measured DigMontage can be supplied with explicit provenance. Never
    represents a template as subject-specific anatomical information.
    """
    copy = raw.copy()
    mne.datasets.eegbci.standardize(copy)
    names = select_eeg(copy)
    if not {"C3", "Cz", "C4"} <= set(names):
        raise ValueError("Geometry requires C3, Cz and C4")
    supplied = montage is not None
    if supplied and (not provenance.strip() or provenance.startswith("MNE 1005")):
        raise ValueError("Supplied geometry requires explicit coordinate provenance")
    name = (
        "colin27_1005" if "colin27_1005" in mne.channels.get_builtin_montages() else "standard_1005"
    )
    montage = mne.channels.make_standard_montage(name) if montage is None else montage
    unmatched = sorted(set(names) - set(montage.ch_names))
    if unmatched:
        raise ValueError(f"Unmatched EEG montage channels: {unmatched}")
    copy.set_montage(montage, match_case=True, on_missing="raise", verbose=False)
    positions = np.asarray([copy.info["chs"][copy.ch_names.index(ch)]["loc"][:3] for ch in names])
    if not np.isfinite(positions).all() or np.any(np.linalg.norm(positions, axis=1) == 0):
        raise ValueError("Electrode positions must be finite nonzero 3D coordinates")
    return copy, {
        "provenance": provenance,
        "template": not supplied,
        "montage_name": name if not supplied else "user supplied",
        "coordinate_frame": "MNE head",
        "units": "m",
        "unmatched": unmatched,
        "positions": {ch: p.tolist() for ch, p in zip(names, positions, strict=True)},
    }
