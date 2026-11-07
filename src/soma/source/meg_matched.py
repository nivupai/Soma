"""Explicit matched MEG fallback: measured coils/device transform, no invented EEG."""

from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.anatomy.config import frozen_config
from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.surfaces import ConductorSurfaces
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Transform


def measured_device_transform(info: Any) -> tuple[Transform, dict[str, Any]]:
    native = info.get("dev_head_t")
    if native is None or int(native["from"]) != 1 or int(native["to"]) != 4:
        raise ValueError("MEG fallback requires measured device-to-head coordinates")
    matrix = np.asarray(native["trans"], dtype=float)
    rotation = matrix[:3, :3]
    orthogonal_error = float(np.max(np.abs(rotation.T @ rotation - np.eye(3))))
    determinant = float(np.linalg.det(rotation))
    # Preserve the acquired matrix verbatim. Its stored precision need not meet
    # the stricter exact-rigid numerical API; substantial shear/scale is rejected.
    if orthogonal_error > 1e-6 or abs(determinant - 1) > 1e-6:
        raise ValueError("Measured device transform is not near a proper rigid rotation")
    transform = Transform(Frame.DEVICE, Frame.HEAD, matrix, rigid=False)
    return transform, {
        "orthogonality_max_error": orthogonal_error,
        "determinant": determinant,
        "near_rigid_tolerance": 1e-6,
        "matrix_modified": False,
        "scope": "acquired near-rigid mapping; generic rigid API tolerance unchanged",
    }


def build_meg_fallback(config_path: Path, output: Path) -> dict[str, Any]:
    cfg = frozen_config(config_path)
    assets = SampleAssets(Path(cfg["root"]), cfg["subject"])
    identity = assets.inspect(modality="meg")
    report = AnatomyReport(
        output, {**cfg, "explicit_mode_override": "MEG_fallback_forward_only"}, identity
    )
    raw = mne.io.read_raw_fif(assets.raw_path, preload=False, verbose=False)
    raw.pick("meg", exclude="bads")
    retained = [p for p in raw.info["projs"] if set(p["data"]["col_names"]) & set(raw.ch_names)]
    raw.del_proj()
    raw.add_proj(retained, remove_existing=True, verbose=False)
    info = raw.info.copy()
    raw.close()
    device, device_quality = measured_device_transform(info)
    with report.stage("surface_QC"):
        surfaces = mne.make_bem_model(
            assets.subject,
            ico=cfg["anatomy"]["bem_ico"],
            conductivity=tuple(cfg["anatomy"]["conductivities_S_m"]),
            subjects_dir=assets.subjects_dir,
            verbose=False,
        )
        conductor = ConductorSurfaces.from_mne(
            assets.subject, surfaces, {"source": "matched participant FLASH-derived boundaries"}
        )
        readiness = conductor.readiness(sensor_compatible=True)
        if readiness["computational_readiness"] != "PASS":
            raise ValueError("MEG geometry fails computational readiness")
    with report.stage("BEM_and_MEG_forward"):
        bem = mne.make_bem_solution(surfaces, verbose=False)
        src = mne.setup_source_space(
            assets.subject,
            spacing=cfg["anatomy"]["source_spacing"],
            surface="white",
            subjects_dir=assets.subjects_dir,
            add_dist=False,
            n_jobs=1,
            verbose=False,
        )
        native = mne.make_forward_solution(
            info,
            trans=assets.transform.to_mne(),
            src=src,
            bem=bem,
            meg=True,
            eeg=False,
            mindist=5,
            n_jobs=1,
            verbose=False,
        )
        mne.write_forward_solution(
            output / "matched-meg-fwd.fif", native, overwrite=False, verbose=False
        )
    return report.finish(
        {
            "status": "matched_MEG_forward_only",
            "mode": "participant_matched_MEG_fallback",
            "subject": assets.subject,
            "sensor_count": len(info["ch_names"]),
            "source_count": native["nsource"],
            "shape": list(native["sol"]["data"].shape),
            "channels": info["ch_names"],
            "channel_units": [int(c["unit"]) for c in info["chs"]],
            "device_to_head_m": device.matrix.tolist(),
            "device_transform_quality": device_quality,
            "head_to_MRI_m": assets.transform.matrix.tolist(),
            "reference": "MEG SSP, no EEG average reference",
            "raw_matrix_condition_reported": False,
            "reason": (
                "mixed magnetometer/gradiometer units require whitening "
                "before cross-channel norm comparisons"
            ),
            "readiness": readiness,
            "anatomical_certification": False,
        }
    )


def apply_meg_inverse(
    info: Any, forward: Any, covariance: Any, evoked: Any, *, lambda2: float = 1 / 9
) -> Any:
    if (
        forward["info"]["ch_names"] != info["ch_names"]
        or evoked.ch_names != info["ch_names"]
        or covariance.ch_names != info["ch_names"]
    ):
        raise ValueError("MEG inverse channel correspondences differ")
    if any(mne.channel_type(info, i) == "eeg" for i in range(len(info["ch_names"]))):
        raise ValueError("MEG fallback does not invent or mix EEG channels")
    operator = mne.minimum_norm.make_inverse_operator(
        info,
        forward,
        loose=0,
        fixed=True,
        depth=0.8,
        noise_cov=covariance,
        rank=None,
        use_cps=False,
        verbose=False,
    )
    return mne.minimum_norm.apply_inverse(
        evoked, operator, lambda2=lambda2, method="MNE", use_cps=False, verbose=False
    )
