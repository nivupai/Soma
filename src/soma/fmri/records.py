"""Functional data retain time, identity and processing-space semantics."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd

from soma.core.provenance import sha256
from soma.geometry.coordinates import validate_affine
from soma.imaging.nifti import load_nifti
from soma.imaging.volumes import Volume


@dataclass(frozen=True)
class FunctionalRun:
    image: Any
    tr: float
    subject: str
    session: str
    task: str
    run: str
    space: str
    events: pd.DataFrame
    confounds: pd.DataFrame
    mask: Volume
    preprocessing: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.image.ndim != 4 or min(self.image.shape) < 1 or self.image.shape[3] < 8:
            raise ValueError("FunctionalRun requires 4D BOLD with at least eight samples")
        if not all([self.subject, self.session, self.task, self.run, self.space]):
            raise ValueError("Explicit subject/session/task/run/space required")
        if not np.isfinite(self.tr) or self.tr <= 0:
            raise ValueError("Finite positive TR seconds required")
        qform, qcode = self.image.get_qform(coded=True)
        sform, scode = self.image.get_sform(coded=True)
        if not qcode and not scode:
            raise ValueError("Functional image needs an explicitly coded spatial transform")
        for matrix in (qform, sform):
            if matrix is not None:
                validate_affine(matrix)
        if qcode and scode and not np.allclose(qform, sform, atol=1e-4, rtol=1e-5):
            raise ValueError(
                "Conflicting functional qform/sform requires explicit upstream resolution"
            )
        spatial, temporal = self.image.header.get_xyzt_units()
        if spatial != "mm" or temporal != "sec":
            raise ValueError(
                "Functional modeling requires explicit mm spatial and sec temporal units"
            )
        if not np.isclose(self.image.header.get_zooms()[3], self.tr, rtol=1e-5, atol=1e-6):
            raise ValueError("BOLD header TR and acquisition metadata disagree")
        native = Volume(
            self.image.dataobj[..., 0], self.image.affine * np.array([0.001] * 3 + [1])[:, None]
        )
        if not native.same_grid(self.mask):
            raise ValueError("BOLD and mask geometry differ; array shape alone is insufficient")
        a = self.mask.array()
        if not np.isin(a, [0, 1]).all() or not np.any(a):
            raise ValueError("Brain/ROI mask must be nonempty binary data")
        if len(self.confounds) != self.n_scans:
            raise ValueError(
                "Confounds must align with every acquisition; no silent volume deletion"
            )
        for index in range(self.n_scans):
            if not np.isfinite(np.asanyarray(self.image.dataobj[..., index])).all():
                raise ValueError("BOLD contains nonfinite intensities")
        if self.preprocessing not in {"validated", "synthetic", "unvalidated-educational"}:
            raise ValueError("Explicit preprocessing status required")
        if not self.provenance.get("source"):
            raise ValueError("Functional source/preprocessing provenance required")
        if self.preprocessing == "validated" and not self.provenance.get("preprocessing_evidence"):
            raise ValueError("Validated preprocessing requires external evidence")
        if self.provenance.get("subject", self.subject) != self.subject:
            raise ValueError("Functional provenance subject mismatch")

    @property
    def n_scans(self) -> int:
        return int(self.image.shape[3])

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return self.subject, self.session, self.task, self.run, self.space


def load_run(
    image: Path,
    *,
    tr: float,
    subject: str,
    session: str,
    task: str,
    run: str,
    space: str,
    events: Path,
    confounds: Path | None,
    mask: Path,
    preprocessing: str,
    provenance: dict[str, Any],
) -> FunctionalRun:
    # Reuse strict Soma qform/sform, units and affine validation on an explicit frame.
    for source_file in [image, events, confounds, mask]:
        if source_file is None:
            continue
        for entity, expected in [("sub", subject), ("ses", session), ("task", task), ("run", run)]:
            found = re.findall(r"(?:^|[/_])" + entity + r"-([A-Za-z0-9]+)", str(source_file))
            if any(value != expected for value in found):
                raise ValueError(
                    "Functional auxiliary file subject/session/task/run identity mismatch"
                )
    native = load_nifti(image, frame=0)
    if native.metadata["source_spatial_units"] != "mm":
        raise ValueError("Convert functional input explicitly to millimetres before modeling")
    bold: Any = nib.load(image, mmap="r")
    nuisance = (
        pd.DataFrame(index=np.arange(bold.shape[3]))
        if confounds is None
        else pd.read_csv(confounds, sep="\t")
    )
    return FunctionalRun(
        bold,
        tr,
        subject,
        session,
        task,
        run,
        space,
        pd.read_csv(events, sep="\t"),
        nuisance,
        load_nifti(mask, kind="labels"),
        preprocessing,
        {
            **provenance,
            "input_sha256": sha256(image),
            "events_sha256": sha256(events),
            "mask_sha256": sha256(mask),
            "confounds_sha256": None if confounds is None else sha256(confounds),
        },
    )
