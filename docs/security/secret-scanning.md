# Secret Scanning Strategy

## Tool Comparison

| Capability | Trufflehog OSS (v2/v3 CLI) | GitHub Advanced Security Secret Scanning |
| --- | --- | --- |
| **Coverage** | Scans local clones, git history, file system paths, Docker/Cloud targets. Works offline and can be run pre-commit or in any CI. | Scans pushes to GitHub repositories (branches, tags, and historical git objects). No local/offline scanning; relies on GitHub SaaS. |
| **Rules & Tuning** | Custom detectors via regex and entropy, allow-list files, baselines, and targeted path filters. Supports curated baselines in-repo (see [`trufflehog-baseline.json`](trufflehog-baseline.json)). | Built-in ~200 provider patterns + custom patterns defined in `.github/secret-scanning.yml`. False-positive suppression managed through GitHub UI or commit/message allow-lists. |
| **Footprint & Dependencies** | Lightweight Python/Go binary; no external services. Fits repo's mixed Python/TypeScript stack without additional runtime. Local pilots possible for contributors without GitHub Enterprise. | Requires GitHub Advanced Security license; scanning occurs server-side which can delay detection for local-only experiments. Cannot be executed within our existing local `scripts/` automation. |
| **Compliance Signals** | Generates JSON artifacts for audit evidence (SOC 2, ISO 27001) that can be stored alongside CI logs. Supports scheduled scans to demonstrate continuous monitoring. | Native integration with GitHub Security Center simplifies evidencing, but relies on GitHub retention (90 days). Exporting artifacts for external audits requires API access. |
| **Alert Routing** | CI workflow can fail builds, upload artifacts, and page on-call via existing incident tooling. | Alerts appear in GitHub Security tab; need additional automation/webhooks to page incident responders. |

**Decision:** Trufflehog OSS remains the primary scanner. It runs locally, surfaces the default-credential templates that exist in this repo, and can be extended via configuration files stored here. GitHub Advanced Security remains optional; enabling it later would provide a secondary control but requires license enablement outside of this code change.

## Baseline Execution

1. Install Trufflehog locally (`pip install trufflehog`) and ensure the repository has a remote named `origin` (needed by legacy CLI).
2. Run the filesystem scan from the repo root:

   ```bash
   python scripts/security/run_trufflehog.py  # or manually:
   trufflehog --json --regex --entropy=False --repo_path . file://.
   ```

3. The JSON findings are persisted to [`docs/security/trufflehog-baseline.json`](trufflehog-baseline.json). Eight findings were recorded on 2025-01-13; all map to sample Postgres/Redis connection strings used in local development templates and infrastructure manifests.
4. Treat the baseline as the allow-list. Confirm any new match is not in that file before updating the baseline.

## False Positive Handling

- **Expected credentials:** Postgres DSNs (`postgresql+psycopg://postgres:postgres@db:5432/theo`) and Redis URLs (`redis://redis:6379/0`) appear in `.env.example`, `infra/docker-compose.yml`, and `theo/services/api/app/core/settings.py` to document local defaults. They are not production secrets.
- **Suppressing noise:** After verifying a finding is a non-sensitive template value, add or update its record in `trufflehog-baseline.json` with the latest commit hash. Baseline entries store the commit path, reason, and string snippet so auditors can trace the exception.
- **Escalation:** If a finding references any credential outside of the documented templates, treat it as a potential leak and follow the remediation steps in [`SECURITY.md`](../../SECURITY.md).

## Continuous Monitoring

The new GitHub Actions workflow (`.github/workflows/secret-scanning.yml`) executes Trufflehog on every push, pull request, and a weekly scheduled run. The job compares live findings against the baseline; the build fails and uploads an artifact if a new secret is detected.

## Future Enhancements

- Enable GitHub Advanced Security when licensing is available to gain cross-repo correlation and integration with GitHub's security dashboard.
- Replace the legacy Python CLI with the Go binary to remove the `origin` remote requirement and improve performance once the CI migration is validated.
- Extend the baseline management script to auto-open issues when a new secret appears instead of only failing CI.
