"""Compatibility facades exposing application-layer entry points.

These modules provide forward-looking import paths for adapters while the
legacy implementation continues to live under ``theo.services``. Once the
migration completes, adapters can depend exclusively on the application
package without touching service-specific modules.
"""

from . import database as database
from . import research as research
from . import runtime as runtime
from . import secret_migration as secret_migration
from . import settings as settings
from . import settings_store as settings_store
from . import version as version
from .database import Base, configure_engine, get_engine, get_session
from .research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    ResearchService,
    get_research_service,
)
from .runtime import allow_insecure_startup
from .secret_migration import migrate_secret_settings
from .settings import (
    Settings,
    get_settings,
    get_settings_cipher,
)
from .settings_store import (
    SETTINGS_NAMESPACE,
    SettingNotFoundError,
    load_setting,
    require_setting,
    save_setting,
)
from .version import get_git_sha

__all__ = [
    "database",
    "research",
    "runtime",
    "secret_migration",
    "settings",
    "settings_store",
    "version",
    "Base",
    "configure_engine",
    "get_engine",
    "get_session",
    "allow_insecure_startup",
    "ResearchService",
    "ResearchNoteDraft",
    "ResearchNoteEvidenceDraft",
    "get_research_service",
    "migrate_secret_settings",
    "Settings",
    "get_settings",
    "get_settings_cipher",
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
    "get_git_sha",
]
