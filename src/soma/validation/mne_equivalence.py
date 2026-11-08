"""Public MNE API comparison under an explicitly equivalent uniform prior."""

from typing import Any

import mne
import numpy as np

from soma.anatomy.synthetic import discrete_sources, synthetic_info
from soma.geometry import Frame, Transform
from soma.source.noise import NoiseModel, average_projector
from soma.source.priors import fit_prior, make_prior


def uniform_mne_agreement(lambda2: float = 1 / 9) -> dict[str, Any]:
    info = synthetic_info()
    positions = np.array(
        [[0.0183, 0.0091, 0.0527], [-0.0231, 0.0173, 0.0309], [0.0117, -0.0131, 0.0153]]
    )
    conductor = mne.make_sphere_model(
        r0=(0, 0, 0),
        head_radius=0.09,
        relative_radii=(0.08 / 0.09, 0.085 / 0.09, 1),
        sigmas=(0.3, 0.006, 0.3),
        verbose=False,
    )
    native = mne.make_forward_solution(
        info,
        trans=Transform(Frame.HEAD, Frame.MRI, np.eye(4)).to_mne(),
        src=discrete_sources(positions),
        bem=conductor,
        eeg=True,
        meg=False,
        mindist=0,
        n_jobs=1,
        verbose=False,
    )
    p = average_projector(len(info.ch_names))
    covariance = mne.Covariance(p, info.ch_names, [], info["projs"], nfree=100)
    noise = NoiseModel(p, tuple(info.ch_names), p)
    lead = p @ native["sol"]["data"]
    ids = tuple(map(str, range(len(positions))))
    prior = make_prior(lead, ids)
    alpha = lambda2 * float(np.sum((noise.whitener @ lead) ** 2)) / noise.rank
    own = fit_prior(lead, prior, noise, alpha=alpha, source_ids=ids)
    op = mne.minimum_norm.make_inverse_operator(
        info,
        native,
        covariance,
        depth=None,
        loose=1,
        fixed=False,
        rank={"eeg": 23},
        use_cps=False,
        verbose=False,
    )
    stc = mne.minimum_norm.apply_inverse(
        mne.EvokedArray(np.eye(24), info, nave=1),
        op,
        lambda2=lambda2,
        method="MNE",
        pick_ori="vector",
        use_cps=False,
        verbose=False,
    )
    expected = np.asarray(stc.data).reshape(9, 24)
    relative = float(np.linalg.norm(own.kernel - expected) / np.linalg.norm(expected))
    if relative > 1e-9:
        raise ValueError(f"MNE uniform-prior agreement failed: {relative}")
    return {
        "relative_kernel_error": relative,
        "lambda2": lambda2,
        "alpha": alpha,
        "MNE_depth": None,
        "loose": 1,
        "rank": 23,
        "reference": "average",
        "equivalence": (
            "Q=I; alpha=lambda2*trace(W L L^T W^T)/rank; MNE source covariance trace/rank scaling"
        ),
        "units": "A m",
        "physical_independence": False,
        "source_count": 3,
    }
