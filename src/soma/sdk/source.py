"""Existing forward/inverse operators; synthetic diagnostics do not validate anatomy."""

from soma.experiments.source_uncertainty import run_uncertainty as run_uncertainty
from soma.source.forward import ForwardModel as ForwardModel
from soma.source.forward import build_forward as build_forward
from soma.source.inverse import CorticalInverse as CorticalInverse
from soma.source.inverse import Tikhonov as Tikhonov
from soma.source.noise import NoiseModel as NoiseModel
from soma.source.noise import average_projector as average_projector
from soma.source.resolution import Resolution as Resolution
from soma.source.template import Template as Template
from soma.source.uncertainty import design as _uncertainty_design
from soma.source.uncertainty import protocol as _uncertainty_protocol

uncertainty_design = _uncertainty_design
uncertainty_protocol = _uncertainty_protocol
