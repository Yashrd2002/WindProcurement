"""Backward-compatibility re-export of application settings."""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
