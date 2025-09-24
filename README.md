# Theo Engine

This repository powers Theo's document ingestion and retrieval pipeline. See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the full system overview. The repository also exposes a bulk ingestion CLI that can walk a folder of source files and hand them to the API or worker pipeline.

Theo Engine now layers grounded generative workflows on top of the deterministic retrieval core:

- Securely store multiple AI provider credentials (OpenAI, Anthropic, Azure, local adapters) and register custom model presets in the admin settings API.
- Run verse-linked research, sermon prep, comparative analysis, multimedia insight extraction, devotional guides, corpus curation, and collaboration flows directly in the Verse Aggregator and search interfaces with strict OSIS-anchored citations.
- Generate export-ready deliverables (Markdown, NDJSON, CSV) for sermons, lessons, and Q&A transcripts with reproducibility manifests, and trigger post-ingest batch enrichments from the CLI.
- Monitor new theological topics via OpenAlex-enhanced clustering and receive weekly digests summarizing under-represented themes.

For usage details run `python -m theo.services.cli.ingest_folder --help` or consult [the CLI guide](docs/CLI.md).

## Running the test suite

The application relies on several third-party libraries for its API, ORM, and ingestion pipeline.
Install the runtime and test dependencies before executing the tests:

```bash
pip install -r requirements.txt
```

After the dependencies are installed you can run `pytest` from the repository root to execute the automated test suite.
