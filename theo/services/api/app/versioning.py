"""API versioning infrastructure.

Provides URL-based API versioning to support backward compatibility
and gradual migration of clients to new API versions.
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, FastAPI


class APIVersion:
    """API version configuration."""

    def __init__(self, version: str, prefix: str | None = None):
        """Initialize API version.

        Args:
            version: Version string (e.g., "1.0", "2.0")
            prefix: URL prefix (defaults to /api/v{major_version})
        """
        self.version = version
        self.major = int(version.split(".")[0])
        self.prefix = prefix or f"/api/v{self.major}"
        self.router = APIRouter(prefix=self.prefix)

    def include_router(
        self,
        router: APIRouter,
        *,
        tags: list[str] | None = None,
        dependencies: list | None = None,
        **kwargs,
    ) -> None:
        """Include a router under this API version."""
        self.router.include_router(
            router,
            tags=tags,
            dependencies=dependencies,
            **kwargs,
        )


class APIVersionManager:
    """Manages multiple API versions and routing."""

    def __init__(self):
        self.versions: dict[str, APIVersion] = {}
        self.default_version: str | None = None

    def register_version(self, version: str, *, is_default: bool = False) -> APIVersion:
        """Register a new API version.

        Args:
            version: Version string (e.g., "1.0")
            is_default: Whether this is the default version (unversioned routes)

        Returns:
            APIVersion instance for router registration
        """
        if version in self.versions:
            return self.versions[version]

        api_version = APIVersion(version)
        self.versions[version] = api_version

        if is_default or self.default_version is None:
            self.default_version = version

        return api_version

    def get_version(self, version: str) -> APIVersion:
        """Get API version by version string."""
        if version not in self.versions:
            raise ValueError(f"API version {version} not registered")
        return self.versions[version]

    def mount_versions(self, app: FastAPI) -> None:
        """Mount all registered API versions to the FastAPI app."""
        for version, api_version in self.versions.items():
            app.include_router(api_version.router, tags=[f"v{api_version.major}"])

            # Mount default version at /api as well
            if version == self.default_version:
                default_router = APIRouter(prefix="/api")
                default_router.include_router(api_version.router)
                # Remove version prefix for default routes
                for route in default_router.routes:
                    if hasattr(route, "path"):
                        route.path = route.path.replace(api_version.prefix, "")
                app.include_router(default_router, tags=["default"])


# Global version manager
_version_manager: APIVersionManager | None = None


def get_version_manager() -> APIVersionManager:
    """Get or create the global API version manager."""
    global _version_manager
    if _version_manager is None:
        _version_manager = APIVersionManager()
    return _version_manager


def versioned_route(version: str) -> Callable:
    """Decorator to register routes under a specific API version.

    Usage:
        @versioned_route("1.0")
        @router.get("/search")
        def search_v1(): ...
    """
    def decorator(func: Callable) -> Callable:
        # Store version metadata on the function
        func.__api_version__ = version  # type: ignore[attr-defined]
        return func
    return decorator


__all__ = [
    "APIVersion",
    "APIVersionManager",
    "get_version_manager",
    "versioned_route",
]
