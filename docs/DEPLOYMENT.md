# Deploying secrets-backed configuration

Theo can derive its Fernet encryption key from external secrets managers so that
application nodes never persist the key in environment variables. The runtime
supports HashiCorp Vault and AWS Secrets Manager. When no backend is configured
Theo falls back to the legacy `SETTINGS_SECRET_KEY` value or, if insecure
startup is enabled, a generated testing key.

## Common environment variables

| Variable | Description |
| --- | --- |
| `SETTINGS_SECRET_BACKEND` | Select the backend used to resolve the Fernet secret (`vault` or `aws`). |
| `SETTINGS_SECRET_NAME` | Identifier or path used when requesting the Fernet secret from the backend. |
| `SETTINGS_SECRET_FIELD` | Optional field name extracted from structured secrets (JSON payloads). |

## HashiCorp Vault

Configure the Vault adapter by pointing Theo at a KV v2 mount. Tokens are read
from the environment at process start.

| Variable | Description |
| --- | --- |
| `SECRETS_VAULT_ADDR` | Vault server URL (e.g. `https://vault.service.consul:8200`). |
| `SECRETS_VAULT_TOKEN` | Token granted read access to the configured secret path. |
| `SECRETS_VAULT_NAMESPACE` | Optional Vault namespace when running under Enterprise Vault. |
| `SECRETS_VAULT_MOUNT_POINT` | KV v2 mount point hosting the secret (defaults to `secret`). |
| `SECRETS_VAULT_VERIFY` | TLS verification flag or CA bundle path passed to the Vault client. |

With these values in place Theo resolves the Fernet secret by issuing a
`read_secret_version` call against the configured mount. The secret payload may
contain multiple keys; specify `SETTINGS_SECRET_FIELD` to extract the correct
value. Missing fields or connection failures are logged and Theo falls back to
its standard `SETTINGS_SECRET_KEY` environment variable.

## AWS Secrets Manager

Theo can also resolve the Fernet secret via AWS Secrets Manager. Configure the
runtime with the following variables:

| Variable | Description |
| --- | --- |
| `SECRETS_AWS_REGION` | AWS region hosting the secret. |
| `SECRETS_AWS_PROFILE` | Optional named profile used when creating the boto3 session. |

The `SETTINGS_SECRET_NAME` value maps to `SecretId` in the AWS API. When the
secret stores structured JSON provide `SETTINGS_SECRET_FIELD` so the adapter can
extract the Fernet value. Binary secrets are base64 decoded before use. Any
failure during resolution is logged and the process reverts to local secret
configuration, matching previous behaviour.

## Backwards compatibility

If no backend variables are provided the service continues to read
`SETTINGS_SECRET_KEY`. Environments that rely on the insecure fallback must set
`THEO_ALLOW_INSECURE_STARTUP=1`; the warning emitted at boot now reflects whether
an external backend was attempted before using the fallback.
