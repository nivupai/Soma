"""Participant-specific MNE BEM/forward integration, distinct from the template path."""

import copy
import time
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.anatomy.cache import cached_object
from soma.anatomy.config import frozen_config
from soma.anatomy.contracts import IndividualModel, validate_eeg_info
from soma.anatomy.surfaces import ConductorSurfaces, distance_to_surface
from soma.core.provenance import sha256
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Points, Transform
from soma.source.forward import ForwardModel


def prepare_sample(
    config_path: Path = Path("configs/individual-source.yaml"),
) -> tuple[SampleAssets, IndividualModel, Any, dict[str, Any]]:
    cfg = frozen_config(config_path)
    if cfg["dataset"] != "mne-sample" or cfg["mode"] != "participant_matched":
        raise ValueError("Individual modeling requires the explicitly matched dataset mode")
    assets = SampleAssets(Path(cfg["root"]), cfg["subject"])
    identity = assets.inspect()
    info = assets.eeg_info()
    started = time.perf_counter()
    native = mne.make_bem_model(
        assets.subject,
        ico=cfg["anatomy"]["bem_ico"],
        conductivity=tuple(cfg["anatomy"]["conductivities_S_m"]),
        subjects_dir=assets.subjects_dir,
        verbose=False,
    )
    surface_preparation_wall = time.perf_counter() - started
    surfaces = ConductorSurfaces.from_mne(
        assets.subject,
        native,
        {
            "source": "distributed participant FLASH-derived boundaries via default symlinks",
            "geometry_preparation": "MNE ico3",
            "assets_sha256": {
                k: v for k, v in identity["assets_sha256"].items() if k.endswith(".surf")
            },
        },
    )
    model = IndividualModel(
        assets.subject,
        assets.subject,
        assets.subject,
        surfaces,
        info,
        assets.transform,
        {
            "sensor_origin": "digitized_EEG",
            "anatomy_origin": "participant_MRI_FLASH",
            "identity": identity,
        },
    )
    parameters = {
        "subject": assets.subject,
        "spacing": cfg["anatomy"]["source_spacing"],
        "surface": "white",
        "add_dist": False,
        "assets": {k: v for k, v in identity["assets_sha256"].items() if k.endswith(".white")},
        "mne": mne.__version__,
    }
    src, source_receipt = cached_object(
        Path("data/derived/individual"),
        "source-space",
        parameters,
        "-src.fif",
        lambda: mne.setup_source_space(
            assets.subject,
            spacing=cfg["anatomy"]["source_spacing"],
            surface="white",
            subjects_dir=assets.subjects_dir,
            add_dist=False,
            n_jobs=1,
            verbose=False,
        ),
        lambda p: mne.read_source_spaces(p, verbose=False),
        lambda p, x: mne.write_source_spaces(p, x, overwrite=False, verbose=False),
    )
    if any(s.get("subject_his_id") != assets.subject for s in src):
        raise ValueError("Individual source-space subject mismatch")
    electrodes = Points(np.array([c["loc"][:3] for c in info["chs"]]), Frame.HEAD)
    distances = distance_to_surface(model.head_to_mri.apply(electrodes), surfaces.meshes[-1])
    sensor_ok = bool(np.max(distances) < 0.03)
    started = time.perf_counter()
    readiness = surfaces.readiness(
        sensor_compatible=sensor_ok,
        minimum_separation_m=cfg["surface_acceptance"]["minimum_separation_m"],
        minimum_quality=cfg["surface_acceptance"]["minimum_triangle_quality"],
    )
    surface_QC_wall = time.perf_counter() - started
    if readiness["computational_readiness"] != "PASS":
        raise ValueError(
            f"Individual conductor/sensor computational readiness fails: {readiness['checks']}"
        )
    return (
        assets,
        model,
        src,
        {
            "identity": identity,
            "readiness": readiness,
            "source_space": source_receipt,
            "preparation_wall_s": {
                "surface_preparation": surface_preparation_wall,
                "surface_QC": surface_QC_wall,
                "source_space_cache": source_receipt["wall_s"],
            },
            "electrode_scalp_distance_m": distances.tolist(),
            "configuration": cfg,
        },
    )


def individual_forward(
    model: IndividualModel,
    src: Any,
    *,
    conductivities: tuple[float, float, float] = (0.3, 0.006, 0.3),
    head_to_mri: Transform | None = None,
    info: Any = None,
    cache_root: Path = Path("data/derived/individual"),
) -> tuple[ForwardModel, dict[str, Any]]:
    transform = head_to_mri or model.head_to_mri
    if transform.source != Frame.HEAD or transform.destination != Frame.MRI or not transform.rigid:
        raise ValueError("Individual forward transform must be rigid head-to-MRI")
    if len(conductivities) != 3 or any(not np.isfinite(c) or c <= 0 for c in conductivities):
        raise ValueError("Positive finite scalp/skull/brain conductivities in S/m required")
    selected_info = model.info if info is None else info
    projector_state = validate_eeg_info(selected_info)
    if selected_info["ch_names"] != model.info["ch_names"]:
        raise ValueError("Sensor ordering changed in individual forward")
    if any(s.get("subject_his_id") != model.subject for s in src):
        raise ValueError("Forward source-space participant mismatch")
    geometry = [
        {
            "id": int(s["id"]),
            "rr_sha256": __import__("hashlib").sha256(s["rr"].tobytes()).hexdigest(),
            "tris_sha256": __import__("hashlib").sha256(s["tris"].tobytes()).hexdigest(),
        }
        for s in model.surfaces.native
    ]
    bem_parameters = {
        "subject": model.subject,
        "geometry": geometry,
        "conductivities_scalp_skull_brain_S_m": list(conductivities),
        "solver": "mne",
        "mne": mne.__version__,
        "numpy": np.__version__,
        "builder_code": sha256(Path(__file__)),
    }

    # This creates a new conductor system for every sigma configuration, never
    # scales a previous BEM matrix. MNE consumes outer-to-inner surface order.
    def conductor() -> Any:
        surfaces = copy.deepcopy(list(reversed(model.surfaces.native)))
        for surface, sigma in zip(surfaces, conductivities, strict=True):
            surface["sigma"] = sigma
        return mne.make_bem_solution(surfaces, solver="mne", verbose=False)

    bem, bem_receipt = cached_object(
        cache_root,
        "BEM",
        bem_parameters,
        "-bem-sol.fif",
        conductor,
        lambda p: mne.read_bem_solution(p, verbose=False),
        lambda p, x: mne.write_bem_solution(p, x, overwrite=False, verbose=False),
    )
    if [int(s["id"]) for s in bem["surfs"]] != [4, 3, 1]:
        raise ValueError("MNE BEM solver requires outer-to-inner scalp/skull/brain ordering")
    if not np.allclose([s["sigma"] for s in bem["surfs"]], conductivities):
        raise ValueError("Stored BEM conductivity correspondence differs")
    coordinates = np.array([ch["loc"][:3] for ch in selected_info["chs"]])
    from soma.imaging.mesh_quality import contains

    moved = transform.apply(Points(coordinates, Frame.HEAD))
    distances = distance_to_surface(moved, model.surfaces.meshes[-1])
    inside = contains(model.surfaces.meshes[-1], moved.xyz)
    # Small apparent penetrations may reflect scalp segmentation/hair/electrode
    # geometry uncertainty; report them explicitly. >3 mm is not accepted.
    if np.any(distances > 0.03):
        raise ValueError("Electrode/scalp discrepancy exceeds 30 mm; no supported scalp projection")
    parameters = {
        "subject": model.subject,
        "BEM": bem_receipt["sha256"],
        "transform": transform.matrix.tolist(),
        "channels": selected_info["ch_names"],
        "sensors_head_m": coordinates.tolist(),
        "electrode_reference_locations_head_m": [
            ch["loc"][:6].tolist() for ch in selected_info["chs"]
        ],
        "projector_state": projector_state,
        "source_normal_sha256": [
            __import__("hashlib").sha256(s["nn"].tobytes()).hexdigest() for s in src
        ],
        "source_vertices": [s["vertno"].tolist() for s in src],
        "source_rr_sha256": [
            __import__("hashlib").sha256(s["rr"].tobytes()).hexdigest() for s in src
        ],
        "orientation": "native_cartesian_then_surface_use_cps_false",
        "reference": "average_retained_EEG",
        "mindist_mm": 5,
        "mne": mne.__version__,
        "numpy": np.__version__,
        "builder_code": sha256(Path(__file__)),
    }
    fwd, receipt = cached_object(
        cache_root,
        "forward",
        parameters,
        "-fwd.fif",
        lambda: mne.make_forward_solution(
            selected_info,
            trans=transform.to_mne(),
            src=src,
            bem=bem,
            meg=False,
            eeg=True,
            mindist=5,
            n_jobs=1,
            verbose=False,
        ),
        lambda p: mne.read_forward_solution(p, verbose=False),
        lambda p, x: mne.write_forward_solution(p, x, overwrite=False, verbose=False),
    )
    native = mne.convert_forward_solution(
        fwd, surf_ori=True, force_fixed=False, use_cps=False, copy=True, verbose=False
    )
    forward = ForwardModel(
        native,
        selected_info,
        {
            "mode": "participant_matched",
            "electrode_scalp_distance_m": distances.tolist(),
            "electrodes_inside_scalp": inside.tolist(),
            "electrodes_more_than_3mm_inside": [
                name
                for name, d, i in zip(selected_info["ch_names"], distances, inside, strict=True)
                if i and d > 0.003
            ],
            "solver_electrode_policy": (
                "MNE standard nearest-scalp barycentric projection; digitization unchanged"
            ),
            "anatomical_sensor_accuracy_certified": False,
            "head_to_MRI_m": transform.matrix.tolist(),
        },
        {
            "subject": model.subject,
            "mode": "participant_matched",
            "surface_provenance": model.surfaces.provenance,
            "conductivity_scalp_skull_brain_S_m": list(conductivities),
            "BEM": bem_receipt,
            "model": model.receipt(),
        },
    )
    return forward, {"BEM": bem_receipt, "forward": receipt}


def require_correspondence(first: ForwardModel, second: ForwardModel) -> None:
    if first.info["ch_names"] != second.info["ch_names"] or first.orientation != second.orientation:
        raise ValueError("Forward channel/orientation correspondence differs")
    second.require_vertices(first.vertices)
    for f in (first, second):
        if f.anatomy.get("mode") != "participant_matched":
            raise ValueError("Do not mix participant and template matrices entrywise")
    if first.anatomy["subject"] != second.anatomy["subject"]:
        raise ValueError("Forward participant mismatch")

    def physical(f: ForwardModel) -> tuple[Any, Any]:
        t = np.asarray(f.geometry["head_to_MRI_m"])
        xyz = f.coordinates.points.xyz @ t[:3, :3].T + t[:3, 3]
        normals = f.native_fixed["source_nn"] @ t[:3, :3].T
        return xyz, normals

    a, na = physical(first)
    b, nb = physical(second)
    if not np.allclose(a, b, atol=1e-7, rtol=0) or not np.allclose(na, nb, atol=1e-6, rtol=0):
        raise ValueError("Physical source positions/normals do not correspond")
