# Metrics Export

The PowerShell service manager writes Prometheus-formatted snapshots to `service_metrics.prom`. The file is regenerated on every health check and can be scraped by sidecar agents or mounted into observability stacks.

The `/metrics` HTTP endpoint exposes the same data if the metrics listener is enabled.
