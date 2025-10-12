# Deployment & Supply-Chain Guidance

## Build Overview

1. Run CI pipelines (`ci.yml`, `security-codeql.yml`, `security-scorecard.yml`).
2. Generate CycloneDX SBOM artifacts for Python and Node dependencies.
3. Build container images using reproducible Dockerfiles (see `theo/services/api/Dockerfile`).
4. Sign images and provenance metadata before publishing to registries.

## Provenance & Signing (SLSA Targets)

| Step | Tooling | Notes |
| --- | --- | --- |
| SBOM | `cyclonedx-bom`, `@cyclonedx/cyclonedx-npm` | Generated automatically in CI; review before release. |
| Provenance | `cosign attest --predicate sbom.json` | Attach SBOM as in-toto predicate for each image. |
| Image Signing | `cosign sign --key $COSIGN_KEY` | Store key material in HSM/KMS; enforce key rotation annually. |
| Verification | `cosign verify` in CD pipeline | Fail deployment if signature missing or invalid. |

## Release Process

1. Tag release (`git tag vX.Y.Z`).
2. Run GitHub Release workflow (future) that:
   - Builds containers for API, worker, CLI images.
   - Uploads SBOM and provenance attestation as release assets.
   - Signs artifacts with cosign key stored in secrets manager.
3. Deploy via infrastructure-as-code (Terraform/Kubernetes) referencing immutable image digests.

## Environment Hardening

- **Secrets:** Provision via cloud secret manager and inject at runtime; do not bake into images.
- **Runtime Policies:** Enable read-only filesystem, non-root users, network policies restricting egress to approved providers.
- **Observability:** Export OpenTelemetry traces + Prometheus metrics for deployment verification.

## Rollback Strategy

- Maintain last two signed releases in registry.
- Automated rollback script validates cosign signatures before redeploying previous version.
- Run smoke tests post-rollback to confirm ingestion/search functionality.

## Change Management

- Require Conventional Commit history and passing CI before promoting a release.
- Document release notes in `docs/changelog/` and reference security fixes explicitly.
- Capture residual risk acceptance in ADRs when deviating from recommended controls.
