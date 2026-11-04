"""Model-family plugins. Importing this package registers the built-in adapters."""
from . import hf_ad, rfdetr_ad, sam3_ad, tensorrt_ad, ultralytics_ad, vlm_ad  # noqa: F401  (register on import)
from .base import (ADAPTERS, Adapter, Availability, Cancelled, Resolved, TrainResult, parse_ref, register,
                   validate_prediction)
from .catalog import catalog, engine_ref, model_conf, resolve

__all__ = ["ADAPTERS", "Adapter", "Availability", "Cancelled", "Resolved", "TrainResult", "catalog", "engine_ref",
           "model_conf", "parse_ref", "register", "resolve", "validate_prediction"]
