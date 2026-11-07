"""Matched coregistration reports, conditional EEG forward and real task reconstruction."""

import time
from pathlib import Path
from typing import Any

import mne
import numpy as np

from soma.anatomy.config import frozen_config
from soma.anatomy.reporting import AnatomyReport
from soma.anatomy.surfaces import distance_to_surface
from soma.anatomy.task_power import short_epoch_band_power
from soma.core.provenance import write_json
from soma.datasets.matched import SampleAssets
from soma.geometry import Frame, Transform
from soma.geometry.coregistration import align_fiducials, icp_align
from soma.source.individual import individual_forward, prepare_sample
from soma.source.inverse import CorticalInverse
from soma.source.noise import NoiseModel


def coregistration_comparison(assets: SampleAssets, model: Any) -> dict[str, Any]:
    head, target, origin = assets.fiducials()
    started = time.perf_counter()
    fit = align_fiducials(head, ("LPA", "nasion", "RPA"), target, ("LPA", "nasion", "RPA"))
    fiducial_wall = time.perf_counter() - started
    reference = mne.coreg.fit_matched_points(
        head.xyz, target.xyz, scale=False, weights=np.ones(3), out="trans"
    )
    hsp = assets.digitized(4)
    started = time.perf_counter()
    icp = icp_align(
        hsp,
        model.surfaces.meshes[-1].vertices,
        model.head_to_mri,
        measurement_kind="digitized_headshape",
    )
    icp_wall = time.perf_counter() - started
    nominal = np.linalg.norm(model.head_to_mri.apply(head).xyz - target.xyz, axis=1)
    exact_hsp = distance_to_surface(model.head_to_mri.apply(hsp), model.surfaces.meshes[-1])
    alternative_hsp = distance_to_surface(icp.transform.apply(hsp), model.surfaces.meshes[-1])
    return {
        "fiducial_origin": origin,
        "registration_wall_s": {"weighted_fiducial_SVD": fiducial_wall, "ICP": icp_wall},
        "primary_head_to_MRI_m": model.head_to_mri.matrix.tolist(),
        "independent_MRI_fiducial_truth_available": False,
        "primary_to_estimated_MRI_fiducials_residual_m": nominal.tolist(),
        "fiducial_20mm_truth_gate": "INDETERMINATE: no measured MRI target fiducials",
        "SVD_fit": fit.diagnostics,
        "SVD_transform_m": fit.transform.matrix.tolist(),
        "SVD_residuals_to_estimated_targets_m": fit.residuals_m.tolist(),
        "established_MNE_SVD_matrix_max_difference": float(
            np.max(np.abs(reference - fit.transform.matrix))
        ),
        "ICP": icp.diagnostics,
        "ICP_transform_m": icp.transform.matrix.tolist(),
        "primary_headshape_exact_surface_distances_m": exact_hsp.tolist(),
        "ICP_headshape_exact_surface_distances_m": alternative_hsp.tolist(),
        "primary_headshape_RMS_m": float(np.sqrt(np.mean(exact_hsp**2))),
        "ICP_headshape_RMS_m": float(np.sqrt(np.mean(alternative_hsp**2))),
        "primary_transform_replaced": False,
        "fit_is_not_true_registration_error": True,
    }


def coregister_workflow(config_path: Path, output: Path) -> dict[str, Any]:
    config = frozen_config(config_path)
    report = AnatomyReport(output, config)
    with report.stage("asset_surface_source_preparation"):
        assets, model, src, prepared = prepare_sample(Path(config["individual_config"]))
    with report.stage("fiducials_and_ICP"):
        result = coregistration_comparison(assets, model)
    for name, matrix in [
        ("primary", model.head_to_mri.matrix),
        ("fiducials", np.array(result["SVD_transform_m"])),
        ("ICP", np.array(result["ICP_transform_m"])),
    ]:
        mne.write_trans(
            output / f"{name}-trans.fif",
            Transform(Frame.HEAD, Frame.MRI, matrix).to_mne(),
            overwrite=False,
            verbose=False,
        )
    write_json(output / "coregistration.json", result)
    from soma.visualization.anatomy import coreg_figures

    coreg_figures(output, assets, model, result)
    return report.finish(
        {
            "status": "complete_conditional_research",
            "subject": model.subject,
            "coregistration": result,
            "readiness": prepared["readiness"],
        }
    )


def validate_bem_workflow(config_path: Path, output: Path) -> dict[str, Any]:
    config = frozen_config(config_path)
    report = AnatomyReport(output, config)
    with report.stage("surface_QC"):
        assets, model, src, prepared = prepare_sample(Path(config["individual_config"]))
    write_json(output / "readiness.json", prepared["readiness"])
    from soma.visualization.anatomy import surface_figures

    surface_figures(output, model.surfaces, prepared["readiness"])
    return report.finish(
        {
            "status": prepared["readiness"]["status"],
            "subject": assets.subject,
            "readiness": prepared["readiness"],
        }
    )


def real_reconstruction(
    assets: SampleAssets, forward: Any, cfg: dict[str, Any], output: Path
) -> dict[str, Any]:
    raw = mne.io.read_raw_fif(assets.raw_path, preload=False, verbose=False)
    events = mne.find_events(
        raw, stim_channel=cfg["real_analysis"]["event_channel"], shortest_event=1, verbose=False
    )
    raw.pick(forward.info["ch_names"])
    raw.del_proj()
    raw.set_eeg_reference("average", projection=True, verbose=False)
    raw.load_data()
    event_ids = cfg["real_analysis"]["event_ids"]
    epochs = mne.Epochs(
        raw,
        events,
        event_id=event_ids,
        tmin=cfg["real_analysis"]["time_window_s"][0],
        tmax=cfg["real_analysis"]["time_window_s"][1],
        baseline=tuple(cfg["real_analysis"]["baseline_s"]),
        proj=True,
        reject={"eeg": cfg["real_analysis"]["reject_eeg_V"]},
        preload=True,
        verbose=False,
    )
    selected = []
    for code in event_ids.values():
        selected.extend(
            np.where(epochs.events[:, 2] == code)[0][
                : cfg["real_analysis"]["maximum_epochs_per_condition"]
            ].tolist()
        )
    if any(np.sum(epochs.events[selected, 2] == code) < 2 for code in event_ids.values()):
        raise ValueError("Insufficient retained sample task epochs")
    selected.sort()
    epochs = epochs[selected]
    covariance = mne.compute_covariance(
        epochs,
        tmin=cfg["real_analysis"]["baseline_s"][0],
        tmax=cfg["real_analysis"]["baseline_s"][1],
        method="shrunk",
        method_params={"shrunk": {"shrinkage": [cfg["inverse"]["shrinkage"]]}},
        rank={"eeg": len(forward.info["ch_names"]) - 1},
        verbose=False,
    )
    covariance.save(output / "background-cov.fif", overwrite=False, verbose=False)
    noise = NoiseModel(
        forward.projector @ covariance.data @ forward.projector,
        tuple(forward.info["ch_names"]),
        forward.projector,
        "pre_stimulus_neural_background_not_pure_instrument_noise",
    )
    inverse = CorticalInverse(
        forward, covariance, lambda2=cfg["inverse"]["lambda2"], depth=cfg["inverse"]["depth"]
    )
    source_data = []
    for stc in inverse.epochs(epochs):
        forward.require_vertices(stc.vertices)
        source_data.append(stc.data)
    array = np.stack(source_data)
    response = (epochs.times >= cfg["real_analysis"]["response_window_s"][0]) & (
        epochs.times <= cfg["real_analysis"]["response_window_s"][1]
    )
    summaries = []
    maps: dict[str, Any] = {}
    powers: dict[str, Any] = {}
    for condition, code in event_ids.items():
        keep = epochs.events[:, 2] == code
        mean = array[keep].mean(axis=0)
        evoked = mne.EvokedArray(
            epochs.get_data(copy=False)[keep].mean(axis=0),
            forward.info.copy(),
            tmin=epochs.tmin,
            nave=1,
        )
        direct = inverse.apply(evoked).data
        maps[condition] = np.sqrt(np.mean(mean[:, response] ** 2, axis=1))
        trial_mu = np.stack(
            [short_epoch_band_power(row, float(epochs.info["sfreq"])) for row in array[keep]]
        )
        evoked_mu = short_epoch_band_power(mean, float(epochs.info["sfreq"]))
        powers[condition + "_trial_mu"] = trial_mu
        powers[condition + "_evoked_mu"] = evoked_mu
        summaries.append(
            {
                "condition": condition,
                "event_code": code,
                "accepted": int(keep.sum()),
                "evoked_linearity_relative_error": float(
                    np.linalg.norm(direct - mean) / np.linalg.norm(mean)
                ),
                "evoked_to_trialwise_mu_power_ratio": float(
                    evoked_mu.sum() / trial_mu.mean(axis=0).sum()
                ),
                "source_RMS_response_peak_Am": float(maps[condition].max()),
                "interpretation": (
                    "exploratory phase-locked response and separate trialwise "
                    "power; no real localization truth"
                ),
            }
        )
    np.savez_compressed(
        output / "sample-task-maps.npz",
        **maps,
        **powers,
        source_vertices_lh=forward.vertices[0],
        source_vertices_rh=forward.vertices[1],
        times_s=epochs.times,
        event_codes=epochs.events[:, 2],
    )
    np.savez_compressed(
        output / "inverse-kernel.npz",
        current_kernel=inverse.kernel,
        background_covariance=noise.covariance,
    )
    # A separate direct MNE call on an identical operator is a reference adapter
    # check, not an independent numerical inverse or anatomical validation.
    ref = mne.minimum_norm.apply_inverse(
        evoked,
        inverse.operator,
        lambda2=cfg["inverse"]["lambda2"],
        method="MNE",
        use_cps=False,
        verbose=False,
    ).data
    comparison = float(np.linalg.norm(ref - direct) / np.linalg.norm(direct))
    raw.close()
    return {
        "conditions": summaries,
        "noise": noise.diagnostics(),
        "event_semantics": "MNE sample audiovisual task, not PhysioNet motor imagery",
        "MNE_reference_adapter_relative_error": comparison,
        "nave": 1,
        "source_units": "A m",
        "power_units": "(A m)^2",
        "trialwise_power_band_Hz": [8, 13],
        "Welch_window_samples": min(int(epochs.info["sfreq"]), array.shape[-1]),
        "Welch_frequency_resolution_Hz": float(epochs.info["sfreq"])
        / min(int(epochs.info["sfreq"]), array.shape[-1]),
        "power_comparison_scope": (
            "short audiovisual epochs; phase and noise average away; not motor imagery"
        ),
        "dropped_epoch_log": [list(x) for x in epochs.drop_log],
        "real_source_truth_available": False,
    }


def build_individual_workflow(config_path: Path, output: Path) -> dict[str, Any]:
    config = frozen_config(config_path)
    report = AnatomyReport(output, config)
    with report.stage("prepare_and_QC"):
        assets, model, src, prepared = prepare_sample(config_path)
    report.source = prepared["identity"]
    with report.stage("coregistration_comparison"):
        coreg = coregistration_comparison(assets, model)
    with report.stage("BEM_and_forward"):
        forward, receipts = individual_forward(
            model, src, conductivities=tuple(config["anatomy"]["conductivities_S_m"])
        )
    write_json(output / "readiness.json", prepared["readiness"])
    write_json(output / "coregistration.json", coreg)
    write_json(output / "forward.json", forward.diagnostics())
    np.savez_compressed(
        output / "individual-forward.npz",
        lead_field=forward.matrix,
        source_head_m=forward.coordinates.points.xyz,
        lh_vertices=forward.vertices[0],
        rh_vertices=forward.vertices[1],
        sensor_head_m=np.array([c["loc"][:3] for c in model.info["chs"]]),
        head_to_MRI_m=model.head_to_mri.matrix,
    )
    with report.stage("real_EEG_inverse"):
        response = real_reconstruction(assets, forward, config, output)
    from soma.visualization.anatomy import coreg_figures, individual_figures, surface_figures

    with report.stage("figures"):
        coreg_figures(output, assets, model, coreg)
        surface_figures(output, model.surfaces, prepared["readiness"])
        individual_figures(output, forward)
    return report.finish(
        {
            "status": "complete_conditional_participant_matched_research",
            "subject": model.subject,
            "readiness_status": prepared["readiness"]["status"],
            "computational_readiness": prepared["readiness"]["computational_readiness"],
            "preparation_wall_s": prepared["preparation_wall_s"],
            "coregistration": coreg,
            "forward_shape": list(forward.matrix.shape),
            "forward_rank": forward.diagnostics()["rank"],
            "physical_caches": receipts,
            "real_EEG": response,
            "anatomical_certification": False,
            "clinical_validation": False,
        }
    )
