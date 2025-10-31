"""Shared helpers for the evidence toolkit."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    import pythonbible as pb
except ModuleNotFoundError:  # pragma: no cover - lightweight environments
    pb = None  # type: ignore[assignment]

import yaml
from pydantic import TypeAdapter

from theo.domain.research.osis import format_osis

_RECORD_ADAPTER = TypeAdapter(list[dict[str, Any]])


def hash_sid(parts: Iterable[str]) -> str:
    """Generate a deterministic short identifier from ``parts``."""

    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


def load_records(path: Path) -> tuple["EvidenceRecord", ...]:
    """Load evidence records from a JSON, JSONL, or Markdown file."""

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        raw: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    elif suffix == ".md":
        raw = _load_markdown_records(path)
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("records") or raw.get("data") or []
        if not isinstance(raw, list):
            raise TypeError(f"Expected list payload in {path}")
    payload = _RECORD_ADAPTER.validate_python(raw)
    from .models import EvidenceRecord  # late import to avoid cycles

    records = tuple(EvidenceRecord.model_validate(item) for item in payload)
    return records


def dump_records(path: Path, records: Sequence["EvidenceRecord"]) -> None:
    """Persist ``records`` as canonical JSON."""

    serializable = [record.model_dump(mode="json") for record in records]
    path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dump_records_jsonl(path: Path, records: Sequence["EvidenceRecord"]) -> None:
    """Persist ``records`` as newline-delimited JSON."""

    payload = [json.dumps(record.model_dump(mode="json"), ensure_ascii=False) for record in records]
    path.write_text("\n".join(payload) + ("\n" if payload else ""), encoding="utf-8")


def _load_markdown_records(path: Path) -> list[dict[str, Any]]:
    from .models import EvidenceRecord  # late import to avoid cycles

    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text, path)
    metadata = yaml.safe_load(frontmatter) or {}

    title = _extract_title(body)
    claim = _extract_between(body, "## Claim", ["### Scope", "## Evidence Summary"])
    summary = _extract_between(
        body,
        "## Evidence Summary",
        ["### Key Excerpts", "## Analysis"],
    )
    scope_block = _extract_between(body, "### Scope", ["## Evidence Summary"])
    primary_ref = _extract_scope_value(scope_block, "Primary Passage")
    related_refs = _extract_scope_value(scope_block, "Related Passages")
    doctrinal_scope = _extract_scope_value(scope_block, "Doctrinal Scope")
    confidence = _extract_scope_value(scope_block, "Confidence")

    excerpt_block = _extract_between(
        body,
        "### Key Excerpts",
        ["### Source Provenance", "## Analysis"],
    )
    key_excerpts = _parse_key_excerpts(excerpt_block)
    sources_block = _extract_between(body, "### Source Provenance", ["## Analysis"])
    sources = _parse_source_table(sources_block)

    analysis_block = _extract_between(
        body,
        "## Analysis",
        ["## Recommended Actions", "## Tags"],
    )
    analysis = _parse_analysis(analysis_block)

    actions_block = _extract_between(body, "## Recommended Actions", ["## Tags", "## Appendices"])
    recommended_actions = _parse_actions(actions_block)
    tags_block = _extract_between(body, "## Tags", ["## Appendices"])
    tags = _parse_tags(tags_block)

    appendices_block = _extract_between(body, "## Appendices", [])
    appendices = _parse_appendices(appendices_block)

    osis_references = _collect_references(
        [
            primary_ref,
            related_refs,
            *(excerpt["reference"] for excerpt in key_excerpts),
        ]
    )

    record_payload: dict[str, Any] = {
        "title": title,
        "summary": summary or None,
        "osis": tuple(sorted(osis_references)) if osis_references else primary_ref or (),
        "tags": tags,
        "metadata": {
            **metadata,
            "claim": claim or None,
            "scope": {
                "primary": primary_ref,
                "related": related_refs,
                "doctrinal": doctrinal_scope,
                "confidence": confidence,
            },
            "key_excerpts": key_excerpts,
            "sources": sources,
            "analysis": analysis,
            "recommended_actions": recommended_actions,
            "appendices": appendices,
            "source_path": str(path),
        },
    }
    record = EvidenceRecord.model_validate(record_payload)
    return [record.model_dump(mode="json")]


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.lstrip().startswith("---"):
        msg = f"Markdown card missing YAML frontmatter: {path}"
        raise ValueError(msg)

    lines = text.splitlines()
    try:
        end_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as exc:  # pragma: no cover - malformed card
        msg = f"Markdown card has unterminated frontmatter: {path}"
        raise ValueError(msg) from exc

    frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return frontmatter, body


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    msg = "Markdown card is missing a title heading"
    raise ValueError(msg)


def _extract_between(text: str, marker: str, end_markers: list[str]) -> str:
    anchor = marker.strip()
    start = text.find(anchor)
    if start == -1:
        return ""
    start = text.find("\n", start)
    if start == -1:
        return ""
    start += 1
    end = len(text)
    for candidate in end_markers:
        if not candidate:
            continue
        idx = text.find(candidate.strip(), start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end].strip()


def _extract_scope_value(scope_block: str, label: str) -> str:
    pattern = re.compile(rf"\*\*{re.escape(label)}:\*\*\s*(.+)")
    for line in scope_block.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).strip()
    return ""


def _parse_key_excerpts(block: str) -> list[dict[str, str]]:
    excerpts: list[dict[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        content = line[1:].strip()
        separator_match = None
        for candidate in re.finditer(r"\s[-–—]\s", content):
            left = content[: candidate.start()].rstrip()
            right = content[candidate.end() :].lstrip()
            if _looks_like_range_boundary(left, right):
                continue
            separator_match = candidate
            break
        if separator_match:
            reference = content[: separator_match.start()].strip()
            snippet = content[separator_match.end() :].strip()
        else:
            reference, snippet = content, ""
            for separator in ("—", "–"):
                if separator in content:
                    reference, snippet = content.split(separator, 1)
                    reference = reference.strip()
                    snippet = snippet.strip()
                    break
            if not snippet:
                hyphen_index = content.rfind(" - ")
                if hyphen_index != -1:
                    candidate_reference = content[:hyphen_index].rstrip()
                    candidate_snippet = content[hyphen_index + 3 :].lstrip()
                    if candidate_snippet and not _RANGE_ONLY_SEGMENT.fullmatch(candidate_snippet):
                        reference, snippet = candidate_reference, candidate_snippet
        excerpts.append({
            "reference": reference.strip(),
            "snippet": snippet.strip(),
        })
    return excerpts


def _looks_like_range_boundary(left: str, right: str) -> bool:
    """Return ``True`` when a spaced dash likely separates a verse range."""

    if not left or not right:
        return False

    if not _RANGE_LEFT_SUFFIX.search(left):
        return False

    return bool(_RANGE_RIGHT_PREFIX.match(right))


_RANGE_LEFT_SUFFIX = re.compile(r"(?:\d+[:\.]?\d*[a-z]?|\d+[a-z]?)\s*$", re.IGNORECASE)


_RANGE_RIGHT_PREFIX = re.compile(
    r"""
    ^
    (?:
        (?:[1-3]\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+
    )?
    \d+(?::\d+)?[a-z]?
    """,
    re.VERBOSE,
)


_RANGE_ONLY_SEGMENT = re.compile(
    r"""
    \d+(?::\d+)?[a-z]?
    (?:\s*[-–—]\s*\d+(?::\d+)?[a-z]?)*
    \s*
    """,
    re.VERBOSE,
)


def _parse_source_table(block: str) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cleaned = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(cleaned) != 4 or cleaned[0] in {"Source", "---"}:
            continue
        source, type_, publication, notes = cleaned
        sources.append(
            {
                "source": source,
                "type": type_,
                "publication": publication,
                "notes": notes,
            }
        )
    return sources


def _parse_analysis(block: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"^\-\s*\*\*(.+?):\*\*\s*(.+)$")
    for line in block.splitlines():
        match = pattern.match(line.strip())
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            result[key] = match.group(2).strip()
    return result


def _parse_actions(block: str) -> list[str]:
    actions: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+\.\s+", stripped):
            actions.append(re.sub(r"^\d+\.\s+", "", stripped))
    return actions


def _parse_tags(block: str) -> tuple[str, ...]:
    if not block:
        return ()
    tags = [tag.strip() for tag in re.split(r",|\n", block) if tag.strip()]
    return tuple(sorted({tag for tag in tags if tag}))


def _parse_appendices(block: str) -> list[dict[str, str]]:
    if not block:
        return []
    appendices: list[dict[str, str]] = []
    segments = re.split(r"^### ", block, flags=re.MULTILINE)
    for segment in segments:
        if not segment.strip():
            continue
        lines = segment.splitlines()
        title = lines[0].strip()
        body = "\n".join(line.rstrip() for line in lines[1:]).strip()
        appendices.append({"title": title, "body": body})
    return appendices


def _collect_references(chunks: Iterable[str]) -> set[str]:
    references: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        if isinstance(chunk, str):
            parts = re.split(r"[,;]", chunk)
        else:
            parts = chunk
        for part in parts:
            text = str(part).strip()
            if not text:
                continue
            normalized_text = text.replace("–", "-").replace("—", "-")
            if pb is None:
                references.add(normalized_text)
                continue
            try:
                entries = pb.get_references(normalized_text)
            except Exception:  # pragma: no cover - pythonbible guard
                references.add(normalized_text)
                continue
            if not entries:
                references.add(normalized_text)
                continue
            references.update(format_osis(entry) for entry in entries)
    return references


__all__ = ["hash_sid", "load_records", "dump_records", "dump_records_jsonl"]
