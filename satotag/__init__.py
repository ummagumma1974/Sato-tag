"""SatoTag: an offline research model, not a Bitcoin consensus modification."""

__version__ = "0.2.0"

from .engine import ValidationError, analyze

__all__ = ["ValidationError", "analyze"]

