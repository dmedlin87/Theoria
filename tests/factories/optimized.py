"""Utilities for caching expensive test data generation."""

from __future__ import annotations

import copy
from typing import Any, ClassVar


class OptimizedTestDataFactory:
    """Generate test data once and reuse cached copies in subsequent tests."""

    _cache: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get_cached_data(cls, data_type: str, **params: Any) -> Any:
        """Return cached data for the requested type, creating it when needed."""

        cache_key = cls._build_cache_key(data_type, params)
        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls._generate_data(data_type, **params)
        return cls._clone(cls._cache[cache_key])

    @classmethod
    def _build_cache_key(cls, data_type: str, params: dict[str, Any]) -> str:
        normalised = tuple(sorted((key, repr(value)) for key, value in params.items()))
        return f"{data_type}:{normalised}"

    @classmethod
    def _generate_data(cls, data_type: str, **params: Any) -> Any:
        if data_type == "verse_data":
            return cls._generate_verse_data(**params)
        if data_type == "user_data":
            return cls._generate_user_data(**params)
        raise ValueError(f"Unsupported data type '{data_type}' for cached test data")

    @staticmethod
    def _clone(value: Any) -> Any:
        if isinstance(value, (dict, list, set, tuple)):
            return copy.deepcopy(value)
        return value

    @staticmethod
    def _generate_verse_data(*, book: str = "Genesis", chapter: int = 1, verses: int = 5) -> dict[str, Any]:
        return {
            "book": book,
            "chapter": chapter,
            "verses": [
                {
                    "number": index + 1,
                    "text": f"Sample verse {index + 1} from {book} {chapter}",
                }
                for index in range(verses)
            ],
        }

    @staticmethod
    def _generate_user_data(*, name: str = "Test User", email: str = "user@example.com") -> dict[str, Any]:
        return {
            "name": name,
            "email": email,
            "preferences": {"newsletter": False, "beta_opt_in": True},
        }
