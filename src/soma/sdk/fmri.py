"""GLM interfaces retain the existing inference policy; human maps are descriptive."""

from soma.fmri.design import Contrast as Contrast
from soma.fmri.design import ModelConfig as ModelConfig
from soma.fmri.design import build_design as build_design
from soma.fmri.glm import Estimate as Estimate
from soma.fmri.glm import Fit as Fit
from soma.fmri.glm import contrast as contrast
from soma.fmri.glm import fit as fit
from soma.fmri.glm import fixed_effects as fixed_effects
from soma.fmri.inference import InferencePolicy as InferencePolicy
from soma.fmri.records import FunctionalRun as FunctionalRun
from soma.fmri.records import load_run as load_run
from soma.fmri.spatial import SpatialChain as SpatialChain
from soma.fmri.spatial import SpatialMap as SpatialMap
from soma.fmri.spatial import align_roi as align_roi
from soma.fmri.spatial import roi_estimates as roi_estimates
