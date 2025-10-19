"""Metadata enrichment via external catalogs."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from theo.services.api.app.persistence_models import Document, Passage
from theo.application.facades.settings import Settings, get_settings

LOGGER = logging.getLogger(__name__)
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"


@dataclass
class EnrichmentResult:
    """Structured metadata extracted from an enrichment provider."""

    provider: str
    raw: dict[str, Any]
    title: str | None = None
    doi: str | None = None
    authors: list[str] | None = None
    venue: str | None = None
    year: int | None = None
    primary_topic: str | None = None
    abstract: str | None = None
    topics: list[str] | None = None


class MetadataEnricher:
    """Populate document metadata using external catalogs."""

    ENRICHMENT_VERSION = 1

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # Public API -----------------------------------------------------------
    def enrich_document(self, session: Session, document: Document) -> bool:
        """Attempt to enrich a document in-place."""

        result = self._resolve(document)
        if result is None:
            return False

        self._apply(document, result)
        session.add(document)
        session.commit()
        return True

    # Resolution helpers ---------------------------------------------------
    def _resolve(self, document: Document) -> EnrichmentResult | None:
        queries = self._build_queries(document)
        if not queries:
            return None

        result = self._try_openalex(queries)
        if result:
            return result

        return self._try_crossref(queries)

    def _build_queries(self, document: Document) -> Sequence[tuple[str, str]]:
        queries: list[tuple[str, str]] = []

        doi = self._extract_doi(document)
        if doi:
            queries.append(("doi", doi))

        if document.source_url:
            queries.append(("url", document.source_url))

        if document.title:
            queries.append(("title", document.title))

        return queries

    # Provider lookups -----------------------------------------------------
    def _try_openalex(
        self, queries: Sequence[tuple[str, str]]
    ) -> EnrichmentResult | None:
        for query_type, value in queries:
            data = self._fetch_openalex(query_type, value)
            if not data:
                continue
            parsed = self._parse_openalex(data)
            if parsed:
                return parsed
        return None

    def _fetch_openalex(self, query_type: str, value: str) -> dict[str, Any] | None:
        fixture = self._load_fixture("openalex", query_type, value)
        if fixture is not None:
            return fixture

        if not value:
            return None

        try:
            if query_type == "doi":
                identifier = value
                if not identifier.lower().startswith("http"):
                    identifier = f"https://doi.org/{identifier}"
                url = f"{OPENALEX_WORKS_URL}/{self._quote(identifier)}"
                payload = self._http_get_json(url)
                if isinstance(payload, dict):
                    return payload
            else:
                params = {"search": value, "per-page": 1}
                url = f"{OPENALEX_WORKS_URL}?{urlencode(params)}"
                payload = self._http_get_json(url)
                if isinstance(payload, dict):
                    results = payload.get("results")
                    if isinstance(results, list) and results:
                        first = results[0]
                        if isinstance(first, dict):
                            return first
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            LOGGER.debug("OpenAlex lookup failed", exc_info=exc)
        return None

    def _parse_openalex(self, data: dict[str, Any]) -> EnrichmentResult | None:
        doi = _normalise_doi(data.get("doi"))
        authors = _extract_authors_from_openalex(data.get("authorships"))
        venue = None
        host_venue = data.get("host_venue")
        if isinstance(host_venue, dict):
            venue = host_venue.get("display_name") or host_venue.get("publisher")

        abstract = _flatten_openalex_abstract(data.get("abstract_inverted_index"))
        topics = _dedupe_preserve_order(_extract_topics(data.get("concepts")))

        return EnrichmentResult(
            provider="openalex",
            raw=data,
            title=data.get("display_name"),
            doi=doi,
            authors=authors or None,
            venue=venue,
            year=_safe_int(data.get("publication_year")),
            primary_topic=topics[0] if topics else None,
            abstract=abstract,
            topics=topics or None,
        )

    def _try_crossref(
        self, queries: Sequence[tuple[str, str]]
    ) -> EnrichmentResult | None:
        for query_type, value in queries:
            data = self._fetch_crossref(query_type, value)
            if not data:
                continue
            parsed = self._parse_crossref(data)
            if parsed:
                return parsed
        return None

    def _fetch_crossref(self, query_type: str, value: str) -> dict[str, Any] | None:
        fixture = self._load_fixture("crossref", query_type, value)
        if fixture is not None:
            return fixture

        if not value:
            return None

        try:
            if query_type == "doi":
                url = f"{CROSSREF_WORKS_URL}/{self._quote(value)}"
                payload = self._http_get_json(url)
            elif query_type == "title":
                params = {"query.title": value, "rows": 1}
                url = f"{CROSSREF_WORKS_URL}?{urlencode(params)}"
                payload = self._http_get_json(url)
            else:
                params = {"query.bibliographic": value, "rows": 1}
                url = f"{CROSSREF_WORKS_URL}?{urlencode(params)}"
                payload = self._http_get_json(url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            LOGGER.debug("Crossref lookup failed", exc_info=exc)
            return None

        if not isinstance(payload, dict):
            return None
        return payload

    def _parse_crossref(self, payload: dict[str, Any]) -> EnrichmentResult | None:
        message = payload.get("message")
        if not isinstance(message, dict):
            message = payload

        items = message.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                message = first

        doi = _normalise_doi(message.get("DOI"))
        authors = _extract_authors_from_crossref(message.get("author"))
        venue = None
        container_titles = message.get("container-title")
        if isinstance(container_titles, list) and container_titles:
            venue = container_titles[0]
        if not venue:
            venue = message.get("publisher")

        abstract_raw = message.get("abstract")
        abstract = _clean_html(abstract_raw) if isinstance(abstract_raw, str) else None
        subject_values = (
            message.get("subject") if isinstance(message.get("subject"), list) else None
        )
        topics = (
            _dedupe_preserve_order(subject_values or []) if subject_values else None
        )
        year = _extract_year_from_crossref(message)

        title_value = message.get("title")
        if isinstance(title_value, list) and title_value:
            title_value = title_value[0]
        if not isinstance(title_value, str):
            title_value = None

        return EnrichmentResult(
            provider="crossref",
            raw=message,
            title=title_value,
            doi=doi,
            authors=authors or None,
            venue=venue,
            year=year,
            primary_topic=topics[0] if topics else None,
            abstract=abstract,
            topics=topics or None,
        )

    # Application ---------------------------------------------------------
    def _apply(self, document: Document, result: EnrichmentResult) -> None:
        existing = document.bib_json if isinstance(document.bib_json, dict) else {}
        bib_copy = dict(existing)
        enrichment_block = bib_copy.get("enrichment")
        if not isinstance(enrichment_block, dict):
            enrichment_block = {}
        raw_payload = result.raw
        if isinstance(raw_payload, dict):
            raw_payload = {k: v for k, v in raw_payload.items() if k != "_fixture"}
        enrichment_block[result.provider] = raw_payload
        bib_copy["enrichment"] = enrichment_block

        if result.title and not document.title:
            document.title = result.title
        if result.doi:
            document.doi = result.doi
        if result.authors:
            document.authors = result.authors
        if result.venue:
            document.venue = result.venue
        if result.year is not None:
            document.year = result.year
        if result.abstract:
            document.abstract = result.abstract
        if result.topics:
            document.topics = {
                "primary": result.primary_topic,
                "all": result.topics,
            }
            if result.primary_topic:
                bib_copy["primary_topic"] = result.primary_topic

        document.enrichment_version = self.ENRICHMENT_VERSION
        document.bib_json = bib_copy

    # Utilities -----------------------------------------------------------
    def _load_fixture(
        self, provider: str, query_type: str, value: str
    ) -> dict[str, Any] | None:
        root = getattr(self.settings, "fixtures_root", None)
        candidates: list[Path] = []
        if root:
            path = Path(root)
            if not path.is_absolute():
                project_root = Path(__file__).resolve().parents[5]
                path = (project_root / path).resolve()
            candidates.append(path)
        candidates.append(Path(__file__).resolve().parents[5] / "fixtures")

        fixtures_root: Path | None = None
        for candidate_root in candidates:
            if candidate_root.exists():
                fixtures_root = candidate_root
                break
        if fixtures_root is None:
            return None

        slug = _slugify(value)
        key = f"{query_type}_{slug}" if slug else query_type
        candidate = fixtures_root / provider / f"{key}.json"
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                LOGGER.debug("Invalid JSON in fixture %s", candidate)
            else:
                if isinstance(payload, dict):
                    payload["_fixture"] = True
                return payload
        return None

    def _http_get_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            data = response.read().decode(charset)
        return json.loads(data)

    def _extract_doi(self, document: Document) -> str | None:
        candidates: list[str] = []
        if document.doi:
            candidates.append(document.doi)
        if isinstance(document.bib_json, dict):
            for key in ("DOI", "doi"):
                value = document.bib_json.get(key)
                if isinstance(value, str):
                    candidates.append(value)
        if document.source_url:
            doi = _extract_doi_from_url(document.source_url)
            if doi:
                candidates.append(doi)

        for candidate in candidates:
            normalised = _normalise_doi(candidate)
            if normalised:
                return normalised
        return None

    def _quote(self, value: str) -> str:
        return quote(value, safe="/:")


# Standalone helper functions ----------------------------------------------


def _slugify(value: str) -> str:
    value = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _normalise_doi(raw: Any) -> str | None:
    if not raw:
        return None
    doi = str(raw).strip()
    if not doi:
        return None
    doi_lower = doi.lower()
    if doi_lower.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi_lower.startswith("http://doi.org/"):
        doi = doi[15:]
    elif doi_lower.startswith("doi:"):
        doi = doi.split(":", 1)[1]
    return doi.strip() or None


def _extract_doi_from_url(url: str) -> str | None:
    if "doi.org" not in url.lower():
        return None
    path = urlsplit(url).path
    if not path:
        return None
    return _normalise_doi(path.lstrip("/"))


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _flatten_openalex_abstract(index: Any) -> str | None:
    if not isinstance(index, dict):
        return None
    positions: dict[int, str] = {}
    max_index = -1
    for word, indexes in index.items():
        if not isinstance(word, str):
            continue
        if isinstance(indexes, Iterable):
            for position in indexes:
                if isinstance(position, int) and position >= 0:
                    positions[position] = word
                    if position > max_index:
                        max_index = position
    if max_index < 0:
        return None
    ordered = [positions.get(i) for i in range(max_index + 1)]
    tokens = [token for token in ordered if isinstance(token, str) and token]
    return " ".join(tokens) if tokens else None


def _extract_topics(concepts: Any) -> list[str]:
    topics: list[str] = []
    if isinstance(concepts, list):
        for concept in concepts:
            if isinstance(concept, dict):
                name = concept.get("display_name") or concept.get("name")
                if isinstance(name, str) and name:
                    topics.append(name)
    return topics


def _extract_authors_from_openalex(authorships: Any) -> list[str]:
    authors: list[str] = []
    if isinstance(authorships, list):
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author_data = authorship.get("author")
            if isinstance(author_data, dict):
                name = author_data.get("display_name") or author_data.get(
                    "display_name_raw"
                )
                if isinstance(name, str) and name:
                    authors.append(name)
    return authors


def _extract_authors_from_crossref(data: Any) -> list[str]:
    authors: list[str] = []
    if isinstance(data, list):
        for author in data:
            if not isinstance(author, dict):
                continue
            given = author.get("given")
            family = author.get("family")
            parts = [part for part in (given, family) if isinstance(part, str) and part]
            if parts:
                authors.append(" ".join(parts))
            else:
                name = author.get("name")
                if isinstance(name, str) and name:
                    authors.append(name)
    return authors


def _extract_year_from_crossref(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "issued"):
        data = message.get(key)
        if isinstance(data, dict):
            date_parts = data.get("date-parts")
            if (
                isinstance(date_parts, list)
                and date_parts
                and isinstance(date_parts[0], list)
                and date_parts[0]
            ):
                year = date_parts[0][0]
                year_int = _safe_int(year)
                if year_int is not None:
                    return year_int
    return None


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return unescape(text).strip()


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item:
            continue
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
