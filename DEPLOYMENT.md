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
| Provenance | `cosign attest --predicate build-attestation.json --type https://theoria.dev/attestations/container-build` | Predicate bundles build metadata plus SBOM digest for downstream verification. |
| Image Signing | `cosign sign --keyless` | GitHub OIDC identity is recorded in the Sigstore transparency log; no long-lived keys required. |
| Verification | `cosign verify` & `cosign verify-attestation` in CD pipeline | Fail deployment if signature or attestation missing/invalid. |

### Automated signing workflow

- The `Release Containers` GitHub Actions workflow (`.github/workflows/deployment-sign.yml`) builds the API container from
  `theo/services/api/Dockerfile`, pushes it to GHCR, and publishes the digest that downstream deployments must consume.
- The job uses GitHub OIDC for **keyless** Sigstore signing (`cosign sign --keyless`) and records the signature in the
  transparency log. Any tampering or re-build without the workflow identity is rejected during verification.
- `anchore/sbom-action` generates the image SBOM and the workflow constructs a `build-attestation.json` predicate that bundles
  the SBOM hash together with Git reference, workflow metadata, and run identifiers. This predicate is signed with
  `cosign attest --type https://theoria.dev/attestations/container-build` so both provenance and bill-of-materials are
  traceable.
- Workflow artifacts (`sbom-image.cdx.json`, `build-attestation.json`, `image-metadata.json`, `image-signature.sig`, and
  `image-provenance.in-toto.jsonl`) are uploaded as run artifacts and published to the matching GitHub release tag to satisfy
  archival requirements.
- Consumers should verify signatures and attestations before rollout:
  ```bash
  IMAGE="ghcr.io/<org>/theoria-api@sha256:<digest>"
  cosign verify \
    --certificate-identity "https://github.com/<org>/<repo>/.github/workflows/deployment-sign.yml@refs/tags/<tag>" \
    --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
    "${IMAGE}"

  cosign verify-attestation \
    --type https://theoria.dev/attestations/container-build \
    --certificate-identity "https://github.com/<org>/<repo>/.github/workflows/deployment-sign.yml@refs/tags/<tag>" \
    --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
    "${IMAGE}"
  ```
  The verification command will fail if the signed identity does not match the repository workflow, if the signature is
  missing, or if the attestation has been revoked.

### Trusting the signing identity

- Cosign keyless signing relies on GitHub's OIDC issuer (`https://token.actions.githubusercontent.com`). The Sigstore
  certificate embeds the workflow identity (`https://github.com/<org>/<repo>/.github/workflows/deployment-sign.yml@<ref>`),
  which must be pinned during verification.
- To audit the transparency log entry for a given digest use `cosign triangulate <image@digest>` which returns the canonical
  bundle references stored in the registry.
- If a compromise requires revoking trust, disable the workflow, rotate the repository environment protection rules, and
  republish using a new tag so downstream automation can mark the previous digest as quarantined.

## Release Process

1. Tag release (`git tag vX.Y.Z`).
2. Push the tag to trigger `Release Containers`. The workflow will build, sign, and attest the API image, then attach the
   SBOM, predicate, signature, and metadata files to the GitHub release associated with the tag.
3. Review the generated assets on the release page. Confirm the attestation references the expected git SHA and SBOM hash.
4. Deploy via infrastructure-as-code (Terraform/Kubernetes) referencing immutable image digests from the release metadata.

## Environment Hardening

- **Secrets:** Provision via cloud secret manager and inject at runtime; do not bake into images.
- **Runtime Policies:** Enable read-only filesystem, non-root users, network policies restricting egress to approved providers.
- **Observability:** Export OpenTelemetry traces + Prometheus metrics for deployment verification.

## Rollback Strategy

- Maintain last two signed releases in registry.
- Automated rollback script validates cosign signatures before redeploying previous version.
- Run smoke tests post-rollback to confirm ingestion/search functionality.
- Escalate any performance anomalies using the [Performance Discrepancy Runbook](docs/runbooks/performance_discrepancy_runbook.md) to ensure DevOps is looped in for load testing and mitigation decisions.

## Change Management

- Require Conventional Commit history and passing CI before promoting a release.
- Document release notes in `docs/changelog/` and reference security fixes explicitly.
- Capture residual risk acceptance in ADRs when deviating from recommended controls.
