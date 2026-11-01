"""LabelDesk Python SDK — thin client over the generated `/api/v1` operation map."""
from ._generated import OPERATIONS
from .client import LabelDesk, LabelDeskError

__all__ = ["LabelDesk", "LabelDeskError", "OPERATIONS"]
__version__ = "0.1.0"
