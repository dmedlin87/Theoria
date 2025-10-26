> **Archived on 2025-10-26**

# Bulk ingestion CLI

The `theo.services.cli.ingest_folder` command walks a folder (or a single file) and
submits every supported asset to the Theo ingestion pipeline. It is intended for
local bulk imports and supports synchronous API execution or background worker
queuing. Configure API credentials before invoking the CLI; see the
[Search API authentication guide](authentication.md) for accepted headers and
environment variables.

## Supported sources

The CLI mirrors the API's file ingestion rules and recognizes the following extensions:

- Markdown/text: `.md`, `.markdown`, `.txt`
- General text files: `.html`, `.htm`, extensionless files
- PDF documents: `.pdf`
- Transcripts: `.vtt`, `.webvtt`, `.srt`, `.json`
- Word documents: `.docx`

Any other file types are ignored.

## Usage

```bash
python -m theo.services.cli.ingest_folder PATH [OPTIONS]
```

Run `python -m theo.services.cli.ingest_folder --help` to review the available
flags and descriptions directly from the command line.

Key options:

- `--mode [api|worker]` &mdash; choose whether to run the synchronous API pipeline directly or enqueue Celery worker jobs. Defaults to `api`.
- `--batch-size N` &mdash; process `N` files per batch. The CLI lists the files in each batch before handing them to the backend.
- `--dry-run` &mdash; print the detected files and their inferred source types without ingesting anything.
- `--meta key=value` &mdash; apply metadata overrides to every file. Values are parsed as JSON when possible (e.g. `--meta 'authors=["Jane"]'`).
- `--post-batch steps` &mdash; request comma-separated post-ingest operations (`summaries`, `tags`, `biblio`) after each API batch. Ignored when running in `worker` mode.

## Network safety for URL ingestion

The CLI and API share the same SSRF protections when ingesting URLs. Each
hostname is resolved via DNS before any HTTP request is issued. The resulting IP
addresses are rejected when they fall within private, loopback, link-local, or
user-specified blocked CIDR ranges. Configure these safeguards via environment
variables or settings overrides:

- `ingest_url_block_private_networks` &mdash; toggle the automatic rejection of
  private, loopback, link-local, and reserved ranges. Enabled by default.
- `ingest_url_blocked_ip_networks` &mdash; extend (or narrow) the blocked CIDR
  ranges. The default list covers the common RFC 1918 and RFC 4193 networks.
- `ingest_url_allowed_hosts` &mdash; optional hostname allowlist. When populated,
  only the listed hosts are eligible for ingestion **after** passing the network
  checks above.

The resolver caches DNS lookups for the lifetime of the process to avoid
repeated queries while still ensuring that every redirect target is validated
against the configured policy.

## Examples

Dry-run a directory to inspect what would be ingested:

```bash
python -m theo.services.cli.ingest_folder ./import --dry-run
```

Ingest a folder in batches of five documents, overriding the collection and author metadata:

```bash
python -m theo.services.cli.ingest_folder ./sermons \
  --batch-size 5 \
  --meta collection=sermons \
  --meta 'authors=["Theo Church"]'
```

Queue files for background processing instead of running the API synchronously:

```bash
python -m theo.services.cli.ingest_folder ./archive --mode worker
```

## Code quality checks

Run Theo's linting and test bundle from the command line using the aggregated helper:

```bash
python -m theo.services.cli.code_quality
```

By default the command lints the `mcp_server` package with `ruff` and runs the MCP-focused pytest suite. Add `--include-mypy` to
execute optional type checking (fails the run only when combined with `--strict`). Use the `--ruff-path`, `--pytest-path`, and
`--mypy-path` options to target different packages or tests, and pass tool-specific arguments via the `--ruff-arg`, `--pytest-arg`,
and `--mypy-arg` flags.

## Export utilities

Bulk exports are available via `theo.services.cli.export_data`.

### Citation exports

The citation exporter now supports APA, Chicago, SBL, BibTeX, and CSL JSON styles. When invoking the
CLI you can select a style with `--style`; the value must be one of `apa`, `chicago`, `sbl`, `bibtex`, or
`csl-json`. The UI reuses the `CitationExport` component (`theo/services/web/app/components/CitationExport.tsx`),
which exposes the same styles, download formats, and an optional Zotero hook for research workflows. Embed the
component inside other pages to inherit the ready-made form logic and download handling.

## Retrieval benchmarking

Use the `rag_eval` command to benchmark reranker candidates or intent-aware prompt
changes against the curated evaluation suites:

```bash
python -m theo.services.cli.rag_eval --dev-path data/eval/rag_dev.jsonl \
  --trace-path data/eval/production_traces.jsonl \
  --output data/eval/reranker_candidate.json
```

Pass `--update-baseline` after validating improvements to persist the new aggregate
scores. Surface the before/after metrics in pull requests so reviewers can confirm the
change meets the tolerances configured in `data/eval/baseline.json`.

### Search exports

Run a hybrid search and save the results to an NDJSON file:

```bash
python -m theo.services.cli.export_data search \
  --query "forgiveness" \
  --collection sermons \
  --format ndjson \
  --output search-results.ndjson
```

### Document exports

Fetch all documents in the `sermons` collection, including passages, and write
them to JSON:

```bash
python -m theo.services.cli.export_data documents \
  --collection sermons \
  --output sermons.json
```

Pass `--no-include-passages` to export metadata only, or `--limit N` to cap the
number of returned documents.

Run metadata enrichment immediately after ingest:

```bash
python -m theo.services.cli.ingest_folder ./sermons \
  --post-batch tags
```

Request additional post-processing steps (summaries plus metadata enrichment and bibliography refresh):

```bash
python -m theo.services.cli.ingest_folder ./sermons \
  --post-batch summaries,tags,biblio
```

Metadata enrichment runs inline with the API ingestion, while bibliography and summary jobs are queued through the API/worker stack. These post-batch operations are only available in API mode because worker jobs do not expose document identifiers immediately.
