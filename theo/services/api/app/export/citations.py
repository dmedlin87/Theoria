"""Utilities for rendering document citations in multiple styles."""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    Sequence,
    TYPE_CHECKING,
    Literal,
    cast,
)

from ..models.export import ExportManifest
from .formatters import build_manifest

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from ..models.documents import DocumentDetailResponse

CitationStyle = Literal["csl-json", "apa", "chicago", "sbl", "bibtex"]


@dataclass
class CitationSource:
    """Normalised bibliographic fields for a citation."""

    document_id: str
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    collection: str | None = None
    source_type: str | None = None
    doi: str | None = None
    source_url: str | None = None
    abstract: str | None = None
    publisher: str | None = None
    location: str | None = None
    pages: str | None = None
    volume: str | None = None
    issue: str | None = None
    topics: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_object(cls, obj: Any) -> "CitationSource":
        mapping = obj if isinstance(obj, Mapping) else None
        document_id = _get_value(obj, mapping, "id", "document_id")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("document_id is required for citation sources")

        metadata = _extract_metadata(obj, mapping)

        return cls(
            document_id=document_id,
            title=_get_value(obj, mapping, "title"),
            authors=_coerce_str_list(_get_value(obj, mapping, "authors")),
            year=_coerce_int(
                _get_value(obj, mapping, "year", "pub_year", "publication_year")
            ),
            venue=_get_value(obj, mapping, "venue", "journal", "container_title"),
            collection=_get_value(obj, mapping, "collection"),
            source_type=_get_value(obj, mapping, "source_type"),
            doi=_normalise_doi(_get_value(obj, mapping, "doi")),
            source_url=_get_value(obj, mapping, "source_url", "url"),
            abstract=_get_value(obj, mapping, "abstract"),
            publisher=_metadata_first(
                metadata,
                "publisher",
                "publisher_name",
                "publication",
                "organization",
                "institution",
            ),
            location=_metadata_first(
                metadata,
                "location",
                "place",
                "city",
                "address",
            ),
            pages=_metadata_first(metadata, "pages", "page_range", "pagination"),
            volume=_metadata_first(metadata, "volume", "vol"),
            issue=_metadata_first(metadata, "issue", "number", "no"),
            topics=_resolve_topics(obj, mapping, metadata),
            metadata=metadata or None,
        )


def _get_value(obj: Any, mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    for key in keys:
        if mapping and key in mapping:
            return mapping[key]
        if hasattr(obj, key):
            return getattr(obj, key)
    if mapping:
        meta = mapping.get("meta") or mapping.get("metadata")
        if isinstance(meta, Mapping):
            for key in keys:
                if key in meta:
                    return meta[key]
    if hasattr(obj, "meta"):
        meta_attr = cast(Any, obj).meta
        if isinstance(meta_attr, Mapping):
            for key in keys:
                if key in meta_attr:
                    return meta_attr[key]
    return None


def _extract_metadata(obj: Any, mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    candidates: Iterable[Any] = []
    if mapping:
        candidates = (
            mapping.get("metadata"),
            mapping.get("meta"),
            mapping.get("bib_json"),
        )
    else:
        candidates = (
            getattr(obj, "metadata", None),
            getattr(obj, "meta", None),
            getattr(obj, "bib_json", None),
        )

    for value in candidates:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _resolve_topics(
    obj: Any,
    mapping: Mapping[str, Any] | None,
    metadata: Mapping[str, Any] | None,
) -> list[str] | None:
    raw_topics = _get_value(obj, mapping, "topics", "tags", "keywords", "subjects")
    topics = _coerce_str_list(raw_topics)
    if topics:
        return topics
    if metadata:
        for key in ("topics", "tags", "keywords", "subjects"):
            value = metadata.get(key)
            topics = _coerce_str_list(value)
            if topics:
                return topics
    return None


def _metadata_first(metadata: Mapping[str, Any] | None, *keys: str) -> str | None:
    if not metadata:
        return None
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        if isinstance(value, Sequence):
            for entry in value:
                if isinstance(entry, str) and entry.strip():
                    return entry.strip()
    return None


def _extract_passages(document: Any) -> list[dict[str, Any]] | None:
    """Return serialisable passage entries for *document* if available."""

    if isinstance(document, Mapping):
        passages = document.get("passages")
    else:
        passages = getattr(document, "passages", None)

    if not passages:
        return None

    serialised: list[dict[str, Any]] = []
    for passage in passages:
        if hasattr(passage, "model_dump"):
            serialised.append(passage.model_dump(mode="json"))
        elif isinstance(passage, Mapping):
            serialised.append(dict(passage))
        else:
            payload: dict[str, Any] = {}
            for field in (
                "id",
                "document_id",
                "osis_ref",
                "page_no",
                "t_start",
                "t_end",
                "text",
                "meta",
            ):
                if hasattr(passage, field):
                    payload[field] = getattr(passage, field)
            if payload:
                serialised.append(payload)

    return serialised or None


def _coerce_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else None
    if isinstance(value, Sequence):
        entries = [str(item).strip() for item in value if str(item).strip()]
        return entries or None
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        digits = value.strip()
        if not digits:
            return None
        if digits.isdigit():
            return int(digits)
    return None


def _normalise_doi(value: Any) -> str | None:
    """Normalise DOI strings to a canonical ``https://doi.org/...`` form."""

    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.startswith("doi:"):
        cleaned = cleaned[4:].strip()
        lowered = cleaned.lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi.org/",
    )
    for prefix in prefixes:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            lowered = cleaned.lower()
            break
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("doi:"):
        cleaned = cleaned[4:].strip()
    http_lower = cleaned.lower()
    doi_http_prefixes = (
        "http://doi.org/",
        "https://doi.org/",
        "http://dx.doi.org/",
        "https://dx.doi.org/",
    )
    if http_lower.startswith("http") and not any(
        http_lower.startswith(prefix) for prefix in doi_http_prefixes
    ):
        return cleaned

    lowered = cleaned.lower()
    if lowered.startswith("http"):
        # Assume fully qualified URLs are already canonical enough.
        return cleaned

    if lowered.startswith("doi:"):
        cleaned = cleaned[len("doi:") :].strip()
        lowered = cleaned.lower()

    # Accept bare domains such as ``doi.org/10.123`` or ``dx.doi.org/10.123``.
    for prefix in ("doi.org/", "dx.doi.org/"):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip("/")
            lowered = cleaned.lower()
            break

    if not cleaned:
        return None

    return f"https://doi.org/{cleaned}"
    lowered = cleaned.lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    )
    for prefix in prefixes:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip(" /")
            lowered = cleaned.lower()
            break
    return cleaned or None


def _normalise_author(name: str) -> dict[str, str]:
    """Return structured author information from a free-form *name* string."""

    candidate = name.strip()
    if not candidate:
        return {"literal": name}

    if "," in candidate:
        family, given = [segment.strip() for segment in candidate.split(",", 1)]
        if family and given:
            return {"given": given, "family": family}
        if family:
            return {"family": family}

    parts = [segment.strip() for segment in candidate.split() if segment.strip()]
    if len(parts) >= 2:
        family = parts[-1]
        given = " ".join(parts[:-1])
        return {"given": given, "family": family}

    return {"literal": candidate}


def _apa_author(author: dict[str, str]) -> str:
    literal = author.get("literal")
    family = author.get("family")
    if family:
        given = author.get("given", "")
        initials = " ".join(f"{segment[0].upper()}." for segment in given.split() if segment)
        if initials:
            return f"{family}, {initials}"
        return family
    return literal or ""


def _chicago_author(author: dict[str, str]) -> str:
    if "family" in author and author.get("family"):
        given = author.get("given")
        if given:
            return f"{author['family']}, {given}"
        return author["family"]
    literal = author.get("literal")
    return literal or ""


def _join_with_and(
    values: Sequence[str], *, use_oxford_comma: bool = True, comma_for_pairs: bool = False
) -> str:
    """
    Join a sequence of strings with 'and', optionally using the Oxford comma and/or a comma for pairs.

    Args:
        values: Sequence of strings to join.
        use_oxford_comma: If True, include a comma before 'and' in lists of three or more items (Oxford comma).
        comma_for_pairs: If True, include a comma before 'and' when joining exactly two items.

    Behavior:
        - For a single entry, returns the entry.
        - For two entries:
            - If comma_for_pairs is True: returns "A, and B"
            - If comma_for_pairs is False: returns "A and B"
        - For three or more entries:
            - If use_oxford_comma is True: returns "A, B, and C"
            - If use_oxford_comma is False: returns "A, B and C"

    Examples:
        >>> _join_with_and(["Alice", "Bob"], use_oxford_comma=True, comma_for_pairs=False)
        'Alice and Bob'
        >>> _join_with_and(["Alice", "Bob"], use_oxford_comma=True, comma_for_pairs=True)
        'Alice, and Bob'
        >>> _join_with_and(["Alice", "Bob", "Carol"], use_oxford_comma=True)
        'Alice, Bob, and Carol'
        >>> _join_with_and(["Alice", "Bob", "Carol"], use_oxford_comma=False)
        'Alice, Bob and Carol'
    """
    entries = [entry.strip() for entry in values if entry and entry.strip()]
    if not entries:
        return ""
    if len(entries) == 1:
        return entries[0]
    if len(entries) == 2:
        if comma_for_pairs:
            return f"{entries[0]}, and {entries[1]}"
        return " and ".join(entries)
    prefix = ", ".join(entries[:-1])
    suffix = entries[-1]
    if use_oxford_comma:
        return f"{prefix}, and {suffix}"
    return f"{prefix} and {suffix}"


def _sbl_author(author: dict[str, str], *, primary: bool) -> str:
    given = author.get("given")
    family = author.get("family")
    if given and family:
        if primary:
            return f"{family}, {given}"
        return f"{given} {family}"
    literal = author.get("literal")
    return literal or ""


def _format_anchor_summary(anchors: Sequence[Mapping[str, Any]]) -> str:
    labels: list[str] = []
    for entry in anchors:
        osis = str(entry.get("osis") or "").strip()
        anchor = str(entry.get("label") or entry.get("anchor") or "").strip()
        if osis and anchor:
            labels.append(f"{osis} ({anchor})")
        elif osis:
            labels.append(osis)
        elif anchor:
            labels.append(anchor)
    return "; ".join(labels)


def _build_csl_entry(source: CitationSource, anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    authors: list[dict[str, str]] = []
    for name in source.authors or []:
        if isinstance(name, str) and name.strip():
            authors.append(_normalise_author(name))

    entry: dict[str, Any] = {
        "id": source.document_id,
        "type": _infer_csl_type(source.source_type),
        "title": source.title,
    }
    if authors:
        entry["author"] = authors
    if source.year:
        entry["issued"] = {"date-parts": [[source.year]]}
    if source.doi:
        entry["DOI"] = source.doi
    if source.source_url:
        entry["URL"] = source.source_url
    if source.venue:
        entry["container-title"] = source.venue
    if source.collection:
        entry["collection-title"] = source.collection
    if source.publisher:
        entry["publisher"] = source.publisher
    if source.location:
        entry["publisher-place"] = source.location
    if source.volume:
        entry["volume"] = source.volume
    if source.issue:
        entry["issue"] = source.issue
    if source.pages:
        entry["page"] = source.pages
    if source.abstract:
        entry["abstract"] = source.abstract

    anchor_entries = _format_anchor_summary(anchors)
    if anchor_entries:
        entry["note"] = "Anchors: " + anchor_entries
    return entry


def _infer_csl_type(source_type: str | None) -> str:
    if not source_type:
        return "article-journal"
    normalized = source_type.lower()
    mapping = {
        "article": "article-journal",
        "journal": "article-journal",
        "book": "book",
        "video": "motion_picture",
        "audio": "song",
        "sermon": "speech",
        "web": "webpage",
        "note": "manuscript",
    }
    for key, value in mapping.items():
        if key in normalized:
            return value
    return "article-journal"


def _format_apa(source: CitationSource, anchors: Sequence[Mapping[str, Any]]) -> str:
    raw_authors = [
        name for name in source.authors or [] if isinstance(name, str) and name.strip()
    ]
    normalised_authors = [
        _apa_author(_normalise_author(name)) for name in raw_authors
    ]
    normalised_authors = [author for author in normalised_authors if author]

    if len(normalised_authors) > 1:
        formatted_authors = ", ".join(normalised_authors[:-1]) + f", & {normalised_authors[-1]}"
    elif normalised_authors:
        formatted_authors = normalised_authors[0]
    elif source.publisher:
        formatted_authors = source.publisher
    else:
        formatted_authors = ""

    year = str(source.year) if source.year else "n.d."
    title = source.title or "Untitled document"
    venue = source.venue or source.collection
    parts: list[str] = []
    if formatted_authors:
        parts.append(formatted_authors)
    parts.append(f"({year}).")
    parts.append(f"{title}.")
    if venue:
        parts.append(f"{venue}.")
    if source.volume and source.issue:
        parts.append(f"{source.volume}({source.issue}).")
    elif source.volume:
        parts.append(f"{source.volume}.")
    if source.pages:
        parts.append(f"pp. {source.pages}.")
    if source.doi:
        parts.append(source.doi)
    elif source.source_url:
        parts.append(source.source_url)
    anchor_entries = _format_anchor_summary(anchors)
    if anchor_entries:
        parts.append(f"Anchors: {anchor_entries}")
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def _format_chicago(source: CitationSource, anchors: Sequence[Mapping[str, Any]]) -> str:
    authors = [_chicago_author(_normalise_author(name)) for name in source.authors or []]
    authors = [author for author in authors if author]
    if len(authors) > 1:
        formatted_authors = ", ".join(authors[:-1]) + f", and {authors[-1]}"
    elif authors:
        formatted_authors = authors[0]
    else:
        formatted_authors = source.publisher or "Unknown"

    year = str(source.year) if source.year else "n.d."
    title = source.title or "Untitled"
    venue = source.venue or source.collection
    segments: list[str] = []
    if venue:
        segments.append(venue)
    if source.publisher:
        segments.append(source.publisher)
    if year:
        segments.append(year)
    if source.pages:
        segments.append(str(source.pages))
    if source.doi:
        segments.append(source.doi)
    elif source.source_url:
        segments.append(source.source_url)

    main_clause = f'{formatted_authors}. "{title}."'
    trailing = ". ".join(
        str(segment).strip().rstrip(".") for segment in segments if str(segment).strip()
    )
    body = main_clause
    if trailing:
        body = f"{body} {trailing}"
    anchor_entries = _format_anchor_summary(anchors)
    if anchor_entries:
        stripped = body.rstrip()
        if not stripped.endswith(('.', '!', '?')):
            body = f"{stripped}."
        else:
            body = stripped
        body = f"{body} Anchors: {anchor_entries}"
    if not body.endswith("."):
        body = body.rstrip(".") + "."
    return body


def _format_sbl(source: CitationSource, anchors: Sequence[Mapping[str, Any]]) -> str:
    raw_authors = [_normalise_author(name) for name in source.authors or []]
    formatted_authors = [
        _sbl_author(author, primary=index == 0)
        for index, author in enumerate(raw_authors)
    ]
    formatted_authors = [author for author in formatted_authors if author]
    if not formatted_authors and source.publisher:
        formatted_authors = [source.publisher]

    title = source.title or "Untitled"
    venue_or_collection = source.venue or source.collection

    details_parts: list[str] = []
    if venue_or_collection:
        details_parts.append(str(venue_or_collection).strip())

    publication_bits: list[str] = []
    if source.publisher:
        publication_bits.append(source.publisher)
    if source.location:
        publication_bits.append(source.location)
    year_text = str(source.year) if source.year else "n.d."
    if publication_bits:
        publication_bits.append(year_text)
        details_parts.append(f"({', '.join(publication_bits)})")
    else:
        details_parts.append(year_text)

    if source.volume and source.issue:
        details_parts.append(f"{source.volume} ({source.issue})")
    elif source.volume:
        details_parts.append(str(source.volume))

    details_text = " ".join(part for part in details_parts if part)
    if source.pages:
        if details_text:
            details_text = f"{details_text}: {source.pages}"
        else:
            details_text = source.pages

    segments: list[str] = []
    authors_segment = _join_with_and(
        formatted_authors,
        comma_for_pairs=True,
    )
    if authors_segment:
        authors_segment = authors_segment.strip()
        if authors_segment.endswith((".", "!", "?")):
            segments.append(authors_segment)
        else:
            segments.append(f"{authors_segment}.")

    title_text = str(title).strip()
    title_segment = f'"{title_text or title}"'
    if title_text and not title_text.endswith((".", "!", "?")):
        title_segment = f'"{title_text}."'
    segments.append(title_segment)
    if details_text:
        if not details_text.endswith(('.', '!', '?')):
            details_text = details_text.rstrip('.') + "."
        segments.append(details_text)

    if source.doi:
        segments.append(f"{source.doi}.")
    elif source.source_url:
        segments.append(f"{source.source_url}.")

    anchor_entries = _format_anchor_summary(anchors)
    if anchor_entries:
        segments.append(f"Anchors: {anchor_entries}.")

    return " ".join(segment.strip() for segment in segments if segment and segment.strip())


def _map_bibtex_type(csl_type: str) -> str:
    mapping = {
        "article-journal": "article",
        "book": "book",
        "motion_picture": "misc",
        "song": "misc",
        "speech": "misc",
        "webpage": "misc",
        "manuscript": "unpublished",
    }
    return mapping.get(csl_type, "misc")


def _bibtex_author(author: dict[str, str]) -> str:
    given = author.get("given")
    family = author.get("family")
    if given and family:
        return f"{family}, {given}"
    literal = author.get("literal")
    return literal or ""


def _format_bibtex(source: CitationSource, anchors: Sequence[Mapping[str, Any]]) -> str:
    csl_type = _infer_csl_type(source.source_type)
    entry_type = _map_bibtex_type(csl_type)
    authors = [
        _bibtex_author(_normalise_author(name)) for name in source.authors or []
    ]
    authors = [author for author in authors if author]

    fields: "OrderedDict[str, str]" = OrderedDict()
    fields["title"] = source.title or "Untitled"
    if authors:
        fields["author"] = " and ".join(authors)
    if source.year:
        fields["year"] = str(source.year)
    if source.venue:
        fields["journal"] = source.venue
    elif source.collection:
        fields["booktitle"] = source.collection
    if source.publisher:
        fields["publisher"] = source.publisher
    if source.location:
        fields["address"] = source.location
    if source.volume:
        fields["volume"] = source.volume
    if source.issue:
        fields["number"] = source.issue
    if source.pages:
        fields["pages"] = source.pages
    if source.doi:
        fields["doi"] = source.doi
    if source.source_url:
        fields["url"] = source.source_url
    if source.abstract:
        fields["abstract"] = source.abstract

    anchor_entries = _format_anchor_summary(anchors)
    if anchor_entries:
        fields["note"] = f"Anchors: {anchor_entries}"

    entries = [(key, value) for key, value in fields.items() if value]
    lines = [f"@{entry_type}{{{source.document_id},"]
    for index, (key, value) in enumerate(entries):
        suffix = "," if index < len(entries) - 1 else ""
        lines.append(f"  {key} = {{{value}}}{suffix}")
    lines.append("}")
    return "\n".join(lines)


def format_citation(
    source: CitationSource,
    *,
    style: CitationStyle,
    anchors: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    anchor_entries = list(anchors or [])
    csl_entry = _build_csl_entry(source, anchor_entries)
    if style == "csl-json":
        citation_text = json.dumps(csl_entry, ensure_ascii=False)
    elif style == "chicago":
        citation_text = _format_chicago(source, anchor_entries)
    elif style == "sbl":
        citation_text = _format_sbl(source, anchor_entries)
    elif style == "bibtex":
        citation_text = _format_bibtex(source, anchor_entries)
    else:
        citation_text = _format_apa(source, anchor_entries)
    return citation_text, csl_entry


def build_citation_export(
    documents: Sequence[DocumentDetailResponse | Mapping[str, Any] | Any],
    *,
    style: CitationStyle,
    anchors: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    filters: Mapping[str, Any] | None = None,
    export_id: str | None = None,
    zotero_callback: Callable[[dict[str, Any], CitationSource], None] | None = None,
) -> tuple[ExportManifest, list[OrderedDict[str, Any]], list[dict[str, Any]]]:
    """Return a manifest, serialisable records, and CSL payloads for *documents*."""

    normalised_sources: list[CitationSource] = []
    for document in documents:
        normalised_sources.append(CitationSource.from_object(document))

    totals = {"citations": len(normalised_sources)}
    manifest = build_manifest(
        export_type="citations",
        filters=dict(filters or {}),
        totals=totals,
        cursor=None,
        next_cursor=None,
        mode=style,
        enrichment_version=None,
        export_id=export_id,
    )

    records: list[OrderedDict[str, Any]] = []
    csl_entries: list[dict[str, Any]] = []
    for document, source in zip(documents, normalised_sources):
        anchor_entries = list(anchors.get(source.document_id, [])) if anchors else []
        citation_text, csl_entry = format_citation(
            source, style=style, anchors=anchor_entries
        )
        csl_entries.append(csl_entry)
        if zotero_callback:
            zotero_callback(csl_entry, source)
        record = OrderedDict()
        record["kind"] = "citation"
        record["document_id"] = source.document_id
        record["style"] = style
        record["citation"] = citation_text
        record["title"] = source.title
        record["authors"] = source.authors
        record["year"] = source.year
        record["venue"] = source.venue
        record["collection"] = source.collection
        record["source_type"] = source.source_type
        record["doi"] = source.doi
        record["source_url"] = source.source_url
        record["publisher"] = source.publisher
        record["location"] = source.location
        record["pages"] = source.pages
        record["volume"] = source.volume
        record["issue"] = source.issue
        if source.topics:
            record["topics"] = source.topics
        if anchor_entries:
            record["anchors"] = anchor_entries
        passages = _extract_passages(document)
        if passages is not None:
            record["passages"] = passages
        record["csl"] = csl_entry
        if source.metadata:
            record["metadata"] = source.metadata
        records.append(record)

    return manifest, records, csl_entries


def render_citation_markdown(
    manifest: ExportManifest, records: Sequence[Mapping[str, Any]]
) -> str:
    """Return a Markdown document with manifest front-matter and citation list."""

    lines = [
        "---",
        f"export_id: {manifest.export_id}",
        f"schema_version: {manifest.schema_version}",
        f"created_at: {manifest.created_at.isoformat()}",
        f"type: {manifest.type}",
    ]
    if manifest.mode:
        lines.append(f"style: {manifest.mode}")
    if manifest.filters:
        lines.append(
            "filters: " + json.dumps(manifest.filters, sort_keys=True, ensure_ascii=False)
        )
    lines.append("---\n")

    for index, record in enumerate(records, start=1):
        citation = str(record.get("citation", "")).strip()
        if not citation:
            citation = "Citation unavailable"
        lines.append(f"{index}. {citation}")
        anchors = record.get("anchors")
        if isinstance(anchors, Sequence) and anchors:
            anchor_summary = _format_anchor_summary(anchors)
            if anchor_summary:
                lines.append(f"   - Anchors: {anchor_summary}")
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "CitationStyle",
    "CitationSource",
    "build_citation_export",
    "format_citation",
    "render_citation_markdown",
]
