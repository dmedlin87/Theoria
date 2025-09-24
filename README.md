# Theo Engine

This repository powers Theo's document ingestion and retrieval pipeline. See [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) for the full system overview. The repository also exposes a bulk ingestion CLI that can walk a folder of source files and hand them to the API or worker pipeline.

For usage details run `python -m theo.services.cli.ingest_folder --help` or consult [the CLI guide](docs/CLI.md).

## Running the test suite

The application relies on several third-party libraries for its API, ORM, and ingestion pipeline.
Install the runtime and test dependencies before executing the tests:

```bash
pip install -r requirements.txt
```

After the dependencies are installed you can run `pytest` from the repository root to execute the automated test suite.
