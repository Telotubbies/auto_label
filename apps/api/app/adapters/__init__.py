"""Model-family plugins. Importing this package registers the built-in adapters."""
from . import sam3_ad, ultralytics_ad  # noqa: F401  (register on import)
from .base import ADAPTERS, Adapter, Availability, TrainResult, parse_ref, register, validate_prediction
from .catalog import catalog, resolve

__all__ = ["ADAPTERS", "Adapter", "Availability", "TrainResult", "catalog", "parse_ref", "register",
           "resolve", "validate_prediction"]
