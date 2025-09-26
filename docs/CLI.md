# Bulk ingestion CLI

The `theo.services.cli.ingest_folder` command walks a folder (or a single file) and
submits every supported asset to the Theo ingestion pipeline. It is intended for
local bulk imports and supports synchronous API execution or background worker
queuing.

## Supported sources

The CLI mirrors the API's file ingestion rules and recognises the following extensions:

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

## Export utilities

Bulk exports are available via `theo.services.cli.export_data`.

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
