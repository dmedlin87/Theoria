# Telemetry Quickstart

Theo Engine workflows now emit traces, metrics, and structured logs so you can
observe each run end-to-end. This guide walks through enabling the local
console exporter, generating a sample workflow run, and inspecting the emitted
signals.

## 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Enable local tracing

Set the environment variable that enables the console span exporter when the
FastAPI app boots:

```bash
export THEO_ENABLE_CONSOLE_TRACES=1
```

When this flag is set the application calls
`theo.services.api.app.telemetry.configure_console_tracer`, wiring the
OpenTelemetry SDK with a console exporter. Spans for each workflow will be
printed to stdout.

## 3. Launch the API locally

```bash
uvicorn theo.services.api.app.main:app --reload --log-level info
```

The server now exposes:

- `/metrics` – Prometheus-formatted counters and histograms.
- Structured workflow logs emitted under the `theo.workflow` logger.
- OpenTelemetry spans emitted to the console exporter.

## 4. Trigger a workflow

Use `curl` (or a tool like [httpie](https://httpie.io/)) to run a workflow. The
example below runs the verse copilot workflow against Psalm 23:

```bash
curl -X POST http://localhost:8000/ai/verse \
  -H 'Content-Type: application/json' \
  -d '{
    "osis": "Ps.23",
    "question": "How does this passage speak about guidance?"
  }'
```

Watch the terminal where `uvicorn` is running—each workflow run will log a
start/completion event, emit a span tree to stdout, and update the Prometheus
metrics.

## 5. Inspect metrics

Prometheus metrics are available from the same server:

```bash
curl http://localhost:8000/metrics | grep theo_workflow
```

You should see counters such as `theo_workflow_runs_total` and the latency
histogram `theo_workflow_latency_seconds`.

## 6. Next steps

- To ship traces elsewhere, configure `opentelemetry-sdk` with the exporter of
  your choice (for example OTLP) before launching the app.
- Point a Prometheus or Grafana agent at the `/metrics` endpoint to persist and
  visualise the counters and histograms.
- Adjust your logging configuration to forward the `theo.workflow` logger to a
  structured log collector.

With these steps you can locally validate that Theo Engine workflows expose
healthy telemetry before wiring them into a full observability stack.

