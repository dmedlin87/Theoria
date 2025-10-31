#!/usr/bin/env python3
"""Check evidence card changes for governance requirements.

This script is intentionally lightweight so it can run in local developer
workflows or CI without additional dependencies. It inspects the git diff for a
revision range (or the working tree) to determine whether any evidence cards in
``evidence/cards`` have changed. When such changes are present it enforces that
at least one commit message in the inspected range contains the ``EC-CHANGE:``
tag so reviewers can quickly identify evidence updates.

Additionally the script emits human-readable warnings when changed evidence
cards intersect with topics defined in ``evidence/registry/watchlist.json``.
Watchlist matches do not fail the check; they only surface extra context for
reviewers.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


EC_COMMIT_TAG = "EC-CHANGE:"
CARDS_ROOT = Path("evidence/cards")
DEFAULT_WATCHLIST_PATH = Path("evidence/registry/watchlist.json")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's magic empty tree hash


class EvidenceCardCheckError(RuntimeError):
    """Raised when the evidence card governance checks fail."""


@dataclass(slots=True)
class EvidenceCard:
    path: Path
    card_id: str
    tags: tuple[str, ...]


@dataclass(slots=True)
class WatchlistTopic:
    identifier: str
    label: str
    tags: tuple[str, ...]


def run_git_command(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise EvidenceCardCheckError(
            "git command failed: "
            + " ".join(args)
            + f"\n{result.stderr.strip()}"
        )
    return result.stdout


def ref_exists(ref: str) -> bool:
    try:
        run_git_command(["rev-parse", "--verify", f"{ref}^{{commit}}"])
    except EvidenceCardCheckError:
        return False
    return True


def determine_base_revision(user_base: str | None, head: str) -> str | None:
    if user_base:
        return user_base

    env_candidates = [
        ("GITHUB_BASE_SHA", None),
        ("PR_BASE_SHA", None),
        ("CI_MERGE_REQUEST_TARGET_BRANCH_SHA", None),
        ("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "origin/{value}"),
        ("GITHUB_BASE_REF", "origin/{value}"),
    ]

    for env, template in env_candidates:
        value = os.getenv(env)
        if not value:
            continue
        candidate = template.format(value=value) if template else value
        if ref_exists(candidate):
            return candidate

    try:
        parent = run_git_command(["rev-parse", f"{head}^"]).strip()
    except EvidenceCardCheckError:
        return None
    return parent


def gather_changed_files(base: str | None, head: str) -> list[str]:
    args = ["diff", "--name-only", "--diff-filter=ACDMRTUXB"]
    if base:
        args.append(f"{base}..{head}")
    else:
        # Diff the head commit against the empty tree when there is no base.
        args.append(f"{EMPTY_TREE}..{head}")
    output = run_git_command(args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def collect_commit_messages(base: str | None, head: str) -> list[str]:
    if base:
        range_args: Iterable[str] = (f"{base}..{head}",)
    else:
        range_args = ("-1", head)

    output = run_git_command(["log", "--format=%H%x1f%B%x1e", *range_args])
    messages: list[str] = []
    for entry in output.split("\x1e"):
        if not entry.strip():
            continue
        try:
            _, body = entry.split("\x1f", 1)
        except ValueError:
            body = entry
        messages.append(body.strip())
    return messages


def extract_front_matter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text

    match = re.search(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}, text

    front_matter_text = match.group(1)
    remainder = text[match.end() :]

    data: dict[str, object] = {}
    for line in front_matter_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        raw_value = value.strip()
        if not key:
            continue
        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            if inner:
                items = [item.strip().strip("'\"") for item in inner.split(",")]
                data[key] = [item for item in items if item]
            else:
                data[key] = []
        else:
            data[key] = raw_value.strip("'\"")
    return data, remainder


def normalise_tag(value: str) -> str:
    return value.strip().lower()


def parse_tags_from_body(body: str) -> set[str]:
    lines = body.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "## tags":
            collecting = True
            continue
        if collecting and stripped.startswith("#") and not stripped.lower().startswith("# tags"):
            break
        if collecting:
            if stripped:
                collected.append(stripped)
    tags: set[str] = set()
    if collected:
        merged = " ".join(collected)
        for raw_tag in merged.split(","):
            normalised = normalise_tag(raw_tag)
            if normalised:
                tags.add(normalised)
    return tags


def parse_card(path: Path) -> EvidenceCard:
    text = path.read_text(encoding="utf-8")
    front_matter, body = extract_front_matter(text)

    tags: set[str] = set()
    front_tags = front_matter.get("tags")
    if isinstance(front_tags, str):
        tags.update(normalise_tag(item) for item in front_tags.split(",") if item.strip())
    elif isinstance(front_tags, Iterable):
        for item in front_tags:
            if isinstance(item, str):
                normalised = normalise_tag(item)
                if normalised:
                    tags.add(normalised)

    tags.update(parse_tags_from_body(body))

    card_id = str(front_matter.get("id") or path.stem)
    return EvidenceCard(path=path, card_id=card_id, tags=tuple(sorted(tags)))


def load_watchlist(path: Path) -> list[WatchlistTopic]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    topics_raw = data.get("topics") if isinstance(data, dict) else None
    if not topics_raw:
        return []

    topics: list[WatchlistTopic] = []
    for entry in topics_raw:
        if not isinstance(entry, dict):
            continue
        identifier = str(entry.get("id") or entry.get("label") or "")
        label = str(entry.get("label") or identifier)
        raw_tags = entry.get("tags")
        tag_values: set[str] = set()
        if isinstance(raw_tags, str):
            tag_values.add(normalise_tag(raw_tags))
        elif isinstance(raw_tags, Iterable):
            for item in raw_tags:
                if isinstance(item, str):
                    normalised = normalise_tag(item)
                    if normalised:
                        tag_values.add(normalised)
        topics.append(
            WatchlistTopic(
                identifier=identifier,
                label=label,
                tags=tuple(sorted(tag_values)),
            )
        )
    return topics


def evaluate_watchlist(cards: Sequence[EvidenceCard], topics: Sequence[WatchlistTopic]) -> list[str]:
    warnings: list[str] = []
    for card in cards:
        card_tags = set(card.tags)
        if not card_tags:
            continue
        for topic in topics:
            topic_tags = set(topic.tags)
            if not topic_tags:
                continue
            intersection = sorted(card_tags & topic_tags)
            if not intersection:
                continue
            warnings.append(
                "Evidence card '{}' matches watchlist topic '{}' via tags: {}".format(
                    card.card_id,
                    topic.label,
                    ", ".join(intersection),
                )
            )
    return warnings


def ensure_commit_tag(messages: Sequence[str]) -> None:
    if any(EC_COMMIT_TAG in message for message in messages):
        return
    raise EvidenceCardCheckError(
        "Evidence card changes detected but no commit message contains the "
        f"required '{EC_COMMIT_TAG}' tag."
    )


def collect_changed_cards(changed_files: Iterable[str]) -> list[Path]:
    card_paths: list[Path] = []
    for raw_path in changed_files:
        if not raw_path:
            continue
        normalized = raw_path.replace("\\", "/")
        if not normalized.startswith(str(CARDS_ROOT).replace("\\", "/")):
            continue
        if not normalized.lower().endswith(".md"):
            continue
        card_paths.append(Path(normalized))
    return card_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate evidence card changes and enforce commit tagging.",
    )
    parser.add_argument("--base", help="Base revision to diff against")
    parser.add_argument("--head", default="HEAD", help="Head revision for the diff (default: HEAD)")
    parser.add_argument(
        "--watchlist",
        default=str(DEFAULT_WATCHLIST_PATH),
        help="Path to the evidence card watchlist JSON file",
    )

    args = parser.parse_args(argv)

    head = args.head
    base = determine_base_revision(args.base, head)

    try:
        changed_files = gather_changed_files(base, head)
    except EvidenceCardCheckError as error:
        print(error, file=sys.stderr)
        return 2

    changed_cards = collect_changed_cards(changed_files)
    if not changed_cards:
        print("No evidence card changes detected.")
        return 0

    try:
        commit_messages = collect_commit_messages(base, head)
    except EvidenceCardCheckError as error:
        print(error, file=sys.stderr)
        return 2

    try:
        ensure_commit_tag(commit_messages)
    except EvidenceCardCheckError as error:
        print(error, file=sys.stderr)
        return 1

    cards: list[EvidenceCard] = []
    missing_cards: list[Path] = []
    for path in changed_cards:
        try:
            cards.append(parse_card(path))
        except FileNotFoundError:
            # Deleted cards should still enforce commit tagging but there is no
            # file to parse for metadata.
            missing_cards.append(path)
            continue

    try:
        topics = load_watchlist(Path(args.watchlist))
    except json.JSONDecodeError as error:
        print(f"Failed to parse watchlist JSON: {error}", file=sys.stderr)
        return 2

    warnings = evaluate_watchlist(cards, topics)

    print("Evidence card changes detected:")
    for card in cards:
        display_tags = ", ".join(card.tags) if card.tags else "(no tags)"
        print(f"  - {card.card_id} [{display_tags}]")
    for path in missing_cards:
        print(f"  - {path} [deleted]")

    if warnings:
        print("\nWatchlist warnings:")
        for warning in warnings:
            print(f"  ! {warning}")
    else:
        print("\nWatchlist warnings: none")

    print("\nCommit tag check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
