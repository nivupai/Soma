"""Existing forward/inverse operators; synthetic diagnostics do not validate anatomy."""

from soma.experiments.nonspherical import run_nonspherical as run_nonspherical
from soma.experiments.source_uncertainty import run_uncertainty as run_uncertainty
from soma.source.forward import ForwardModel as ForwardModel
from soma.source.forward import build_forward as build_forward
from soma.source.inverse import CorticalInverse as CorticalInverse
from soma.source.inverse import Tikhonov as Tikhonov
from soma.source.noise import NoiseModel as NoiseModel
from soma.source.noise import average_projector as average_projector
from soma.source.nonspherical import design as _nonspherical_design
from soma.source.nonspherical import head_parameters as _synthetic_head
from soma.source.nonspherical import protocol as _nonspherical_protocol
from soma.source.nonspherical import validate_meshes as _validate_head_meshes
from soma.source.resolution import Resolution as Resolution
from soma.source.template import Template as Template
from soma.source.uncertainty import design as _uncertainty_design
from soma.source.uncertainty import protocol as _uncertainty_protocol

uncertainty_design = _uncertainty_design
uncertainty_protocol = _uncertainty_protocol

nonspherical_design = _nonspherical_design
nonspherical_protocol = _nonspherical_protocol
synthetic_head = _synthetic_head
validate_head_meshes = _validate_head_meshes
