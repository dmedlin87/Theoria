# Theo Engine

This repository powers Theo's document ingestion and retrieval pipeline. See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the full system overview. The repository also exposes a bulk ingestion CLI that can walk a folder of source files and hand them to the API or worker pipeline.

For usage details run `python -m theo.services.cli.ingest_folder --help` or consult [the CLI guide](docs/CLI.md).
