> **Archived on 2025-10-26**

# Lighthouse CI automation

This repository runs automated Lighthouse audits against the staging site via GitHub Actions.

## Configuration files

- `.lighthouserc.json` defines the staging URL that will be audited along with the minimum
  category scores enforced by `lhci assert`. The configuration also sets Chrome flags that are
  required in CI (headless execution, sandbox and shared-memory tweaks, plus certificate error
  suppression) so audits are resilient to staging TLS interstitials.
- `.github/workflows/lighthouse.yml` provisions Node.js, installs `@lhci/cli`, verifies the
  staging host is reachable with the configured credentials, executes `lhci autorun`, and
  uploads the resulting reports as build artifacts.
- `.lighthouseci/baseline/manifest.json` (not committed) should contain the baseline
  Lighthouse results saved from a known-good deployment. The workflow compares new runs
  against this manifest when it is present.

## Required secrets

| Secret | Purpose |
| --- | --- |
| `LHCI_GITHUB_TOKEN` | A classic personal access token or GitHub App installation token with `repo` scope so Lighthouse CI can read commit metadata when it posts build context. |
| `STAGING_BASIC_AUTH_USERNAME` (optional) | Username for HTTP basic auth protecting the staging site. Exposed to the workflow as `LHCI_BASIC_AUTH_USER`. |
| `STAGING_BASIC_AUTH_PASSWORD` (optional) | Password for HTTP basic auth protecting the staging site. Exposed to the workflow as `LHCI_BASIC_AUTH_PASSWORD`. |
| `LHCI_UPLOAD_TOKEN` (optional) | Token required when uploading reports to a remote Lighthouse CI server. Not required for filesystem uploads but reserved for future use. |

Add the secrets under repository Settings → Secrets and variables → Actions. The workflow passes
`LHCI_GITHUB_TOKEN` to `lhci autorun` so the CLI can authenticate with the GitHub API while leaving
other scopes locked down.

If the staging site requires additional headers (for example, API keys or preview tokens), define
matching secrets and map them to the environment variables consumed by Lighthouse using the
`ci.collect.settings.extraHeaders` block in `.lighthouserc.json`.

## Maintaining baselines

1. Run `lhci autorun --config=.lighthouserc.json --upload.target=filesystem --upload.outputDir=.lighthouseci/baseline`
   locally (or download the artifact from a passing workflow run).
2. Copy the generated `manifest.json` into `.lighthouseci/baseline/` and commit the update.
3. Subsequent workflow runs read the committed manifest and log score deltas for the tracked
   categories. The job only fails when the defined score thresholds are violated, avoiding noisy
   issue creation when Lighthouse performance stays within the acceptable range.

The workflow uploads the most recent reports as build artifacts so they can be inspected without
rerunning Lighthouse. If the staging host is ever unreachable, the job now fails fast during the
connectivity check instead of surfacing the less-actionable Chrome interstitial error later in the
`lhci` run.
