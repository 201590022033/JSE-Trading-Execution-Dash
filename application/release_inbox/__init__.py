"""Explicit, inactive release ingestion. Never imported by app startup."""
from .protocol import Rejection, SupportedProfile, load_profiles
from .store import ReleaseInbox, StorageError

__all__ = ["ReleaseInbox", "StorageError", "Rejection", "SupportedProfile", "load_profiles"]
