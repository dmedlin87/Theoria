"""Compatibility shim for relocated research datasets."""
from __future__ import annotations

from theo.data import research as _research

files = _research.files
open_binary = _research.open_binary
open_text = _research.open_text
read_binary = _research.read_binary
read_text = _research.read_text

__all__ = ["files", "open_binary", "open_text", "read_binary", "read_text"]

# Ensure ``importlib.resources.files("theo.services.api.app.research.data")``
# continues to resolve the relocated assets.
__path__ = _research.__path__
if __spec__ is not None and _research.__spec__ is not None:  # pragma: no cover - import hook
    __spec__.submodule_search_locations = _research.__spec__.submodule_search_locations
