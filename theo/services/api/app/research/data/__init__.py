"""
Compatibility shim for relocated research datasets.

Migration guidance:
    Old imports: theo.services.api.app.research.data.*
    New imports: theo.data.research.*

Downstream consumers should update their imports to use the new path proactively.

Deprecation notice:
    This compatibility shim is scheduled for removal in v2.0.
    Please migrate to the new import path as soon as possible.
"""
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
