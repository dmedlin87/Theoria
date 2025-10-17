"""Lightweight OpenAlex client for topic discovery and enrichment."""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

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
    """Minimal client used to retrieve topics and metadata from OpenAlex."""

    API_ROOT = "https://api.openalex.org"
    WORKS_PATH = "/works"
    MAX_RETRIES = 3
    RATE_LIMIT_STATUS = 429
    DEFAULT_BACKOFF = 1.0
    DEFAULT_PAGE_SIZE = 200

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        *,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ) -> None:
        self._owns_client = http_client is None
        if http_client is None:
            http_client = httpx.Client(timeout=httpx.Timeout(10.0, read=20.0))
        self._client = http_client
        self._max_retries = max_retries or self.MAX_RETRIES
        self._backoff = backoff_seconds or self.DEFAULT_BACKOFF

    # ------------------------------------------------------------------
    @property
    def _works_url(self) -> str:
        return f"{self.API_ROOT}{self.WORKS_PATH}"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # Public API --------------------------------------------------------
    def fetch_topics(self, doi: str | None = None, title: str | None = None) -> list[str]:
        """Retrieve ordered topics for a work using DOI or title lookups."""

        payload = self.fetch_work_metadata(doi=doi, title=title, select=("concepts",))
        return self._parse_topics(payload)

    def fetch_work_metadata(
        self,
        *,
        doi: str | None = None,
        title: str | None = None,
        openalex_id: str | None = None,
        select: Sequence[str] | None = None,
    ) -> Mapping[str, Any] | None:
        """Fetch a work record using the available identifiers."""

        queries: list[tuple[str, str]] = []
        if openalex_id:
            queries.append(("id", openalex_id))
        if doi:
            queries.append(("doi", doi))
        if title:
            queries.append(("title", title))

        for query_type, value in queries:
            try:
                if query_type == "id":
                    data = self._fetch_by_id(value, select=select)
                else:
                    data = self._fetch(query_type, value, select=select)
            except httpx.HTTPError:
                continue
            if data:
                return data
        return None

    def fetch_authorships(self, work_id: str) -> list[Mapping[str, Any]]:
        payload = self._fetch_by_id(work_id, select=("authorships",))
        if not isinstance(payload, Mapping):
            return []
        authorships = payload.get("authorships")
        if not isinstance(authorships, Sequence):
            return []
        return [item for item in authorships if isinstance(item, Mapping)]

    def fetch_concepts(self, work_id: str) -> list[Mapping[str, Any]]:
        payload = self._fetch_by_id(work_id, select=("concepts",))
        if not isinstance(payload, Mapping):
            return []
        concepts = payload.get("concepts")
        if not isinstance(concepts, Sequence):
            return []
        return [item for item in concepts if isinstance(item, Mapping)]

    def fetch_citations(
        self,
        work_id: str,
        *,
        max_results: int | None = 50,
    ) -> dict[str, Any]:
        """Fetch citation metadata for the supplied work."""

        metadata = self._fetch_by_id(
            work_id, select=("referenced_works", "cited_by_count")
        )
        referenced: list[str] = []
        if isinstance(metadata, Mapping):
            referenced_raw = metadata.get("referenced_works")
            if isinstance(referenced_raw, Sequence):
                referenced = [str(item) for item in referenced_raw if isinstance(item, str)]

        cited_by: list[dict[str, Any]] = []
        for item in self._paginate(
            f"{self.WORKS_PATH}/{self._normalise_work_id(work_id)}/cited-by",
            max_results=max_results,
        ):
            summary = self._summarise_citation(item)
            if summary:
                cited_by.append(summary)

        return {
            "referenced": referenced,
            "cited_by": cited_by,
        }

    # Internal helpers --------------------------------------------------
    def _fetch(
        self, query_type: str, value: str, *, select: Sequence[str] | None = None
    ) -> Mapping[str, Any] | None:
        if not value:
            return None

        params = self._build_params(select)

        if query_type == "doi":
            identifier = value
            if not identifier.lower().startswith("http"):
                identifier = f"https://doi.org/{identifier}"
            url = f"{self._works_url}/{identifier}"
            payload = self._request_json(url, params=params)
            return payload if isinstance(payload, Mapping) else None

        params = {**params, "search": value, "per-page": 1}
        payload = self._request_json(self._works_url, params=params)
        if isinstance(payload, Mapping):
            results = payload.get("results")
            if isinstance(results, Sequence) and results:
                first = results[0]
                if isinstance(first, Mapping):
                    return first
        return None

    def _fetch_by_id(
        self, work_id: str, *, select: Sequence[str] | None = None
    ) -> Mapping[str, Any] | None:
        if not work_id:
            return None
        params = self._build_params(select)
        identifier = self._normalise_work_id(work_id)
        url = f"{self._works_url}/{identifier}"
        payload = self._request_json(url, params=params)
        return payload if isinstance(payload, Mapping) else None

    def _request_json(
        self, url: str, *, params: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any] | None:
        attempts = 0
        while True:
            response = self._client.get(url, params=params)
            if response.status_code == self.RATE_LIMIT_STATUS and attempts < self._max_retries:
                attempts += 1
                delay = self._retry_delay(response)
                time.sleep(delay)
                continue
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, Mapping) else None

    def _paginate(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        max_results: int | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        query = dict(params or {})
        query.setdefault("per-page", self.DEFAULT_PAGE_SIZE)
        query.setdefault("cursor", "*")

        total = 0
        url = f"{self.API_ROOT}{path}" if path.startswith("/") else f"{self.API_ROOT}/{path.lstrip('/')}"

        while True:
            try:
                payload = self._request_json(url, params=query)
            except httpx.HTTPError:
                return
            if not isinstance(payload, Mapping):
                return
            results = payload.get("results")
            if not isinstance(results, Sequence):
                return
            for item in results:
                if isinstance(item, Mapping):
                    yield item
                    total += 1
                    if max_results is not None and total >= max_results:
                        return
            meta = payload.get("meta")
            next_cursor = None
            if isinstance(meta, Mapping):
                next_cursor = meta.get("next_cursor")
            if not next_cursor:
                return
            query["cursor"] = next_cursor

    def _retry_delay(self, response: httpx.Response) -> float:
        header = response.headers.get("Retry-After")
        try:
            if header:
                return max(float(header), 0.0)
        except (TypeError, ValueError):
            pass
        return self._backoff

    def _build_params(self, select: Sequence[str] | None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if select:
            joined = ",".join(str(item) for item in select if item)
            if joined:
                params["select"] = joined
        return params

    def _parse_topics(self, payload: Mapping[str, Any] | None) -> list[str]:
        if not isinstance(payload, Mapping):
            return []

        concepts = payload.get("concepts")
        if not isinstance(concepts, Sequence):
            return []

        names: list[str] = []
        for concept in concepts:
            if isinstance(concept, Mapping):
                name = concept.get("display_name")
                if isinstance(name, str):
                    names.append(name)
        return _dedupe(names)

    def _summarise_citation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        identifier = payload.get("id")
        if isinstance(identifier, str):
            summary["id"] = identifier
        display_name = payload.get("display_name")
        if isinstance(display_name, str):
            summary["display_name"] = display_name
        doi = payload.get("doi")
        if isinstance(doi, str):
            summary["doi"] = doi
        year = payload.get("publication_year")
        if isinstance(year, int):
            summary["publication_year"] = year
        authorships = payload.get("authorships")
        if isinstance(authorships, Sequence):
            authors: list[str] = []
            for item in authorships:
                if isinstance(item, Mapping):
                    author = item.get("author")
                    if isinstance(author, Mapping):
                        name = author.get("display_name")
                        if isinstance(name, str):
                            authors.append(name)
            if authors:
                summary["authors"] = _dedupe(authors)
        return summary

    def _normalise_work_id(self, work_id: str) -> str:
        value = work_id.strip()
        if not value:
            return value
        prefix = "https://openalex.org/"
        if value.startswith(prefix):
            return value[len(prefix) :]
        return value


__all__ = ["OpenAlexClient"]
