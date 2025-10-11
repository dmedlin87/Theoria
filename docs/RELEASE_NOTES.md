# Release notes

## Unreleased

- Harden URL ingestion against SSRF by resolving each hostname (including
  redirects) before fetching content, rejecting private, loopback, link-local, or
  user-defined blocked networks while caching DNS lookups for performance.
  Configuration knobs: `ingest_url_block_private_networks`,
  `ingest_url_blocked_ip_networks`, and `ingest_url_allowed_hosts`.
- Corrected the guardrail error copy for unparsable citations to match our
  preferred spelling in customer-facing messages.
