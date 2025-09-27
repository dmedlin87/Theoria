"""Lightweight OpenAlex client for topic discovery."""

from __future__ import annotations

from typing import Iterable, Sequence

import httpx


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


class OpenAlexClient:
    """Minimal client used to retrieve topics from OpenAlex."""

    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, http_client: httpx.Client | None = None):
        self._owns_client = http_client is None
        if http_client is None:
            http_client = httpx.Client(timeout=httpx.Timeout(10.0, read=20.0))
        self._client = http_client

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_topics(self, doi: str | None = None, title: str | None = None) -> list[str]:
        """Retrieve ordered topics for a work using DOI or title lookups."""

        queries: list[tuple[str, str]] = []
        if doi:
            queries.append(("doi", doi))
        if title:
            queries.append(("title", title))

        for query_type, value in queries:
            try:
                data = self._fetch(query_type, value)
            except httpx.HTTPError:
                continue
            topics = self._parse_topics(data)
            if topics:
                return topics
        return []

    # ------------------------------------------------------------------
    def _fetch(self, query_type: str, value: str) -> dict | None:
        if not value:
            return None

        if query_type == "doi":
            identifier = value
            if not identifier.lower().startswith("http"):
                identifier = f"https://doi.org/{identifier}"
            response = self._client.get(f"{self.BASE_URL}/{identifier}")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None

        params = {"search": value, "per-page": 1}
        response = self._client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, Sequence) and results:
                first = results[0]
                if isinstance(first, dict):
                    return first
        return None

    def _parse_topics(self, payload: dict | None) -> list[str]:
        if not isinstance(payload, dict):
            return []

        concepts = payload.get("concepts")
        if not isinstance(concepts, Sequence):
            return []

        names: list[str] = []
        for concept in concepts:
            if isinstance(concept, dict):
                name = concept.get("display_name")
                if isinstance(name, str):
                    names.append(name)
        return _dedupe(names)


__all__ = ["OpenAlexClient"]
