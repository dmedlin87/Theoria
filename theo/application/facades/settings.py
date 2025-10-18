"""Application configuration for the Theo Engine API."""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from collections.abc import Callable
from typing import Annotated, Any, Literal
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .runtime import allow_insecure_startup
from ..ports.secrets import SecretRequest, SecretRetrievalError, build_secrets_adapter

LOGGER = logging.getLogger(__name__)


class _BaseEventSink(BaseModel):
    """Common fields shared by event sink configurations."""

    name: str | None = None
    enabled: bool = True


class KafkaEventSink(_BaseEventSink):
    """Configuration for Kafka-based event sinks."""

    backend: Literal["kafka"] = "kafka"
    topic: str
    bootstrap_servers: str
    producer_config: dict[str, Any] = Field(default_factory=dict)
    flush_timeout_seconds: float | None = Field(
        default=1.0,
        description="Optional timeout (in seconds) for producer flush operations.",
    )


class RedisStreamEventSink(_BaseEventSink):
    """Configuration for Redis Streams sinks."""

    backend: Literal["redis_stream"] = "redis_stream"
    stream: str
    redis_url: str | None = None
    maxlen: int | None = None
    approximate_trim: bool = True


EventSink = Annotated[KafkaEventSink | RedisStreamEventSink, Field(discriminator="backend")]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./theo.db", description="SQLAlchemy database URL"
    )
    redis_url: str = Field(
        default="redis://redis:6379/0", description="Celery broker URL"
    )
    storage_root: Path = Field(
        default=Path("./storage"), description="Location for persisted artifacts"
    )
    storage_public_base_url: str | None = Field(
        default=None,
        description="Optional base URL for referencing persisted artifacts",
    )
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    embedding_cache_size: int | None = Field(
        default=1024,
        description="Maximum number of embedding vectors retained in the in-memory cache",
    )
    reranker_enabled: bool = Field(default=False)
    reranker_model_path: Path | None = Field(default=None)
    reranker_model_sha256: str | None = Field(
        default=None,
        description="Expected SHA256 digest for the configured reranker model",
    )
    reranker_model_registry_uri: str | None = Field(
        default=None,
        description="MLflow registry URI for the reranker checkpoint (e.g. models:/theoria/Production)",
    )
    mlflow_tracking_uri: str | None = Field(
        default=None,
        description="Optional MLflow tracking server URI (defaults to MLflow's built-in client)",
    )
    mlflow_registry_uri: str | None = Field(
        default=None,
        description="Optional MLflow model registry URI for CI/dev environments",
    )
    max_chunk_tokens: int = Field(default=900)
    doc_max_pages: int = Field(default=5000)
    transcript_max_window: float = Field(default=40.0)
    ingest_normalized_snapshot_max_bytes: int | None = Field(
        default=1_000_000,
        description=(
            "Maximum number of bytes embedded into normalized snapshots before"
            " switching to an external manifest"
        ),
    )
    fixtures_root: Path | None = Field(
        default=None, description="Optional fixtures path for offline resources"
    )
    user_agent: str = Field(default="Theoria/1.0")
    llm_default_model: str | None = Field(
        default=None, description="Default model identifier for generative features"
    )
    llm_models: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Bootstrap LLM model definitions loaded from the environment.",
    )
    openai_api_key: str | None = Field(
        default=None, description="Optional OpenAI API key"
    )
    openai_base_url: str | None = Field(
        default=None, description="Override base URL for OpenAI-compatible APIs"
    )
    notification_webhook_url: str | None = Field(
        default=None,
        description="Endpoint for dispatching notification webhooks",
    )
    notification_webhook_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers applied to webhook notifications",
    )
    notification_timeout_seconds: float = Field(
        default=10.0, description="HTTP timeout when delivering notifications"
    )
    event_sinks: list[EventSink] = Field(
        default_factory=list,
        description="Collection of event sink configurations for domain events.",
    )
    ingest_web_timeout_seconds: float = Field(
        default=10.0,
        description="HTTP timeout when fetching remote URLs for ingestion",
    )
    ingest_web_max_bytes: int | None = Field(
        default=4 * 1024 * 1024,
        description="Maximum number of bytes fetched when ingesting a web page",
    )
    ingest_web_max_redirects: int = Field(
        default=5,
        description="Maximum redirect hops allowed when fetching web documents",
    )
    case_builder_enabled: bool = Field(
        default=False,
        description="Enable ingestion and APIs for the Case Builder feature",
    )
    case_builder_web_enabled: bool = Field(
        default=False,
        description="Expose Case Builder UI affordances in the web client",
    )
    case_builder_notify_channel: str = Field(
        default="case_object_upsert",
        description="Postgres NOTIFY channel used for case object upsert events",
    )
    graph_projection_enabled: bool = Field(
        default=False,
        description="Enable projecting documents and relationships into a graph store",
    )
    graph_neo4j_uri: str | None = Field(
        default=None,
        description="Bolt URI for the Neo4j instance used for graph projection",
    )
    graph_neo4j_username: str | None = Field(
        default=None,
        description="Username for the Neo4j graph projection adapter",
    )
    graph_neo4j_password: str | None = Field(
        default=None,
        description="Password for the Neo4j graph projection adapter",
    )
    graph_neo4j_database: str | None = Field(
        default=None,
        description="Optional Neo4j database name for graph projection",
    )
    topic_digest_ttl_seconds: int = Field(
        default=3600,
        description="Time-to-live in seconds before regenerating cached topic digests",
    )
    settings_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SETTINGS_SECRET_KEY", "settings_secret_key"),
        description="Secret used to derive the Fernet key for persisted settings",
    )
    settings_secret_backend: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SETTINGS_SECRET_BACKEND", "SETTINGS_SECRET_BACKEND"
        ),
        description="Secrets backend used to resolve the settings secret (e.g. vault, aws)",
    )
    settings_secret_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SETTINGS_SECRET_NAME", "SETTINGS_SECRET_NAME"
        ),
        description="Identifier used by the configured secrets backend to load the settings secret",
    )
    settings_secret_field: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SETTINGS_SECRET_FIELD", "SETTINGS_SECRET_FIELD"
        ),
        description="Optional field extracted from structured secrets (JSON payloads)",
    )
    secrets_vault_addr: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_VAULT_ADDR", "SECRETS_VAULT_ADDR"
        ),
        description="Vault server address used for secret resolution",
    )
    secrets_vault_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_VAULT_TOKEN", "SECRETS_VAULT_TOKEN"
        ),
        description="Vault access token used when querying secrets",
    )
    secrets_vault_namespace: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_VAULT_NAMESPACE", "SECRETS_VAULT_NAMESPACE"
        ),
        description="Optional Vault namespace for secret lookups",
    )
    secrets_vault_mount_point: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_VAULT_MOUNT_POINT", "SECRETS_VAULT_MOUNT_POINT"
        ),
        description="Vault KV v2 mount point containing the settings secret",
    )
    secrets_vault_verify: bool | str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_VAULT_VERIFY", "SECRETS_VAULT_VERIFY"
        ),
        description="TLS verification flag or CA bundle path for Vault requests",
    )
    secrets_aws_profile: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_AWS_PROFILE", "SECRETS_AWS_PROFILE"
        ),
        description="Optional AWS profile name for Secrets Manager",
    )
    secrets_aws_region: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_SECRETS_AWS_REGION", "SECRETS_AWS_REGION"
        ),
        description="AWS region hosting the configured secret",
    )
    api_keys: str | list[str] = Field(
        default="",
        validation_alias=AliasChoices("THEO_API_KEYS", "API_KEYS"),
        description="List of accepted API keys for first-party integrations",
    )
    auth_jwt_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_SECRET", "AUTH_JWT_SECRET"),
        description="Shared secret used to validate bearer JWTs",
    )
    auth_jwt_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_AUTH_JWT_PUBLIC_KEY", "AUTH_JWT_PUBLIC_KEY"
        ),
        description=(
            "PEM-encoded RSA public key or filesystem path used to validate asymmetric JWTs"
        ),
    )
    auth_jwt_public_key_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "THEO_AUTH_JWT_PUBLIC_KEY_PATH", "AUTH_JWT_PUBLIC_KEY_PATH"
        ),
        description="Filesystem path to a PEM-encoded RSA public key for JWT validation",
    )
    auth_jwt_audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_AUDIENCE", "AUTH_JWT_AUDIENCE"),
        description="Optional audience claim enforced for JWT authentication",
    )
    auth_jwt_issuer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("THEO_AUTH_JWT_ISSUER", "AUTH_JWT_ISSUER"),
        description="Optional issuer claim enforced for JWT authentication",
    )
    auth_jwt_algorithms: str | list[str] = Field(
        default="HS256",
        validation_alias=AliasChoices(
            "THEO_AUTH_JWT_ALGORITHMS", "AUTH_JWT_ALGORITHMS"
        ),
        description="Allowed signing algorithms for validating JWTs",
    )
    auth_allow_anonymous: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "THEO_AUTH_ALLOW_ANONYMOUS", "AUTH_ALLOW_ANONYMOUS"
        ),
        description="Allow unauthenticated requests (intended for testing only)",
    )

    @field_validator("auth_allow_anonymous", mode="before")
    @classmethod
    def _parse_bool_with_comment(cls, value: object) -> bool | str:
        """Strip inline comments from boolean values."""
        if isinstance(value, str):
            # Remove inline comments (e.g., "1  # comment" -> "1")
            cleaned = value.split("#")[0].strip()
            return cleaned
        return value
    cors_allowed_origins: str | list[str] = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        validation_alias=AliasChoices(
            "THEO_CORS_ALLOWED_ORIGINS",
            "CORS_ALLOWED_ORIGINS",
        ),
        description=(
            "Comma-separated list of allowed CORS origins for the FastAPI service"
        ),
    )

    @staticmethod
    def _parse_json_or_comma_collection(
        value: object,
        *,
        default: list[str] | None = None,
        transform: Callable[[str], str] | None = None,
        error_message: str = "Invalid list configuration",
    ) -> list[str]:
        import json

        def apply_transform(item: object) -> str | None:
            item_str = str(item).strip()
            if not item_str:
                return None
            if transform is not None:
                item_str = transform(item_str)
            return item_str

        default_value = list(default) if default is not None else []

        if value in (None, ""):
            return list(default_value)

        if isinstance(value, str):
            value_stripped = value.strip()
            if value_stripped.startswith("[") and value_stripped.endswith("]"):
                try:
                    parsed = json.loads(value_stripped)
                except (json.JSONDecodeError, ValueError):
                    parsed = None
                if isinstance(parsed, list):
                    items = [
                        transformed
                        for transformed in (apply_transform(item) for item in parsed)
                        if transformed
                    ]
                    return items or list(default_value)
            items = [
                transformed
                for transformed in (apply_transform(segment) for segment in value.split(","))
                if transformed
            ]
            return items or list(default_value)

        if isinstance(value, list):
            items = [
                transformed
                for transformed in (apply_transform(item) for item in value)
                if transformed
            ]
            return items or list(default_value)

        raise ValueError(error_message)

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, value: object) -> list[str]:
        return cls._parse_json_or_comma_collection(
            value, default=[], error_message="Invalid API key configuration"
        )

    @field_validator("auth_jwt_algorithms", mode="before")
    @classmethod
    def _parse_algorithms(cls, value: object) -> list[str]:
        return cls._parse_json_or_comma_collection(
            value,
            default=["HS256"],
            transform=lambda item: item.upper(),
            error_message="Invalid JWT algorithm configuration",
        )
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        return cls._parse_json_or_comma_collection(
            value, default=[], error_message="Invalid CORS origin configuration"
        )

    def has_auth_jwt_credentials(self) -> bool:
        return bool(
            self.auth_jwt_secret
            or (self.auth_jwt_public_key and self.auth_jwt_public_key.strip())
            or self.auth_jwt_public_key_path
        )

    def load_auth_jwt_public_key(self) -> str | None:
        key_candidate = (self.auth_jwt_public_key or "").strip()
        if key_candidate:
            if "-----BEGIN" in key_candidate:
                return key_candidate
            possible_path = Path(key_candidate).expanduser()
            if possible_path.exists():
                try:
                    return possible_path.read_text(encoding="utf-8")
                except OSError:
                    return None
        if self.auth_jwt_public_key_path:
            try:
                return self.auth_jwt_public_key_path.read_text(encoding="utf-8")
            except OSError:
                return None
        return None

    @staticmethod
    def _parse_string_collection(value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [segment.strip() for segment in value.split(",") if segment.strip()]
        if isinstance(value, (list, tuple, set)):
            cleaned: list[str] = []
            for item in value:
                item_str = str(item).strip()
                if item_str:
                    cleaned.append(item_str)
            return cleaned
        raise ValueError("Invalid list configuration")

    @field_validator(
        "ingest_url_allowed_schemes",
        "ingest_url_blocked_schemes",
        "ingest_url_allowed_hosts",
        "ingest_url_blocked_hosts",
        "ingest_url_blocked_ip_networks",
        mode="before",
    )
    @classmethod
    def _parse_ingest_collections(cls, value: object) -> list[str]:
        return cls._parse_string_collection(value)

    @model_validator(mode="after")
    def _validate_reranker_configuration(self) -> "Settings":
        # Only validate reranker configuration if reranker is enabled
        if not self.reranker_enabled:
            return self

        if self.reranker_model_path and self.reranker_model_registry_uri:
            raise ValueError(
                "Configure either reranker_model_path or reranker_model_registry_uri, not both"
            )

        if self.reranker_model_registry_uri:
            if self.reranker_model_sha256:
                raise ValueError(
                    "reranker_model_sha256 is not supported with reranker_model_registry_uri"
                )
            return self

        if self.reranker_model_path is None:
            if self.reranker_model_sha256:
                raise ValueError(
                    "reranker_model_sha256 requires reranker_model_path to be set"
                )
            return self

        allowed_root = (self.storage_root / "rerankers").resolve()
        resolved_path = self.reranker_model_path
        if not resolved_path.is_absolute():
            resolved_path = (allowed_root / resolved_path).resolve()
        else:
            resolved_path = resolved_path.resolve()

        if not resolved_path.is_relative_to(allowed_root):
            raise ValueError(
                "reranker_model_path must reside within the rerankers directory"
            )

        digest = self.reranker_model_sha256
        if not digest:
            raise ValueError(
                "reranker_model_sha256 is required when reranker_model_path is set"
            )

        normalized_digest = digest.lower()
        if re.fullmatch(r"[0-9a-f]{64}", normalized_digest) is None:
            raise ValueError(
                "reranker_model_sha256 must be a 64 character hexadecimal digest"
            )

        self.reranker_model_path = resolved_path
        self.reranker_model_sha256 = normalized_digest
        return self
    contradictions_enabled: bool = Field(
        default=True, description="Toggle contradiction search endpoints"
    )
    geo_enabled: bool = Field(
        default=True, description="Toggle geography lookup endpoints"
    )
    creator_verse_perspectives_enabled: bool = Field(
        default=True,
        description="Toggle aggregated creator perspectives by verse",
    )
    creator_verse_rollups_async_refresh: bool = Field(
        default=False,
        description="Queue creator verse rollup refreshes via Celery instead of inline",
    )
    verse_timeline_enabled: bool = Field(
        default=True,
        description="Toggle verse mention timeline aggregation endpoints",
    )
    intent_tagger_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("INTENT_TAGGER_ENABLED", "intent_tagger_enabled"),
        description="Toggle automatic tagging of chat intents",
    )
    intent_model_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("INTENT_MODEL_PATH", "intent_model_path"),
        description="Path to the trained intent classification model",
    )
    ingest_upload_max_bytes: int = Field(
        default=16 * 1024 * 1024,
        description="Maximum allowed size for synchronous ingest uploads in bytes",
    )
    simple_ingest_allowed_roots: list[Path] = Field(
        default_factory=list,
        description=(
            "Filesystem roots permitted for simple ingest requests. Local ingest is "
            "disabled until explicit roots are configured."
        ),
    )
    ingest_url_allowed_schemes: list[str] = Field(
        default_factory=lambda: ["http", "https"],
        description="Allowed URL schemes for ingestion requests.",
    )
    ingest_url_blocked_schemes: list[str] = Field(
        default_factory=lambda: ["file", "gopher"],
        description="URL schemes explicitly blocked for ingestion requests.",
    )
    ingest_url_allowed_hosts: list[str] = Field(
        default_factory=list,
        description=(
            "Optional hostname allowlist for URL ingestion. When non-empty only "
            "listed hosts are permitted."
        ),
    )
    ingest_url_blocked_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "::1"],
        description="Hostnames blocked from URL ingestion.",
    )
    ingest_url_blocked_ip_networks: list[str] = Field(
        default_factory=lambda: [
            "127.0.0.0/8",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "169.254.0.0/16",
            "::1/128",
            "fc00::/7",
            "fe80::/10",
        ],
        description="CIDR ranges blocked from URL ingestion.",
    )
    ingest_url_block_private_networks: bool = Field(
        default=True,
        description=(
            "Block URLs that resolve to private, loopback, or link-local addresses."
        ),
    )
    mcp_tools_enabled: bool = Field(
        default=False,
        description="Expose Model Context Protocol tooling under the /mcp sub-application.",
    )
    mcp_schema_base_url: str = Field(
        default="https://theoengine.dev/mcp/schemas",
        description="Base URL used when emitting MCP JSON Schema identifiers.",
    )
    mcp_write_allowlist: str | None = Field(
        default=None,
        description=(
            "Optional comma-separated allowlist entries (tool=value) gating MCP write tools."
        ),
    )
    mcp_write_rate_limits: str | None = Field(
        default=None,
        description=(
            "Optional comma-separated rate limits per MCP tool (e.g. note_write=5/min)."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    if settings.fixtures_root is None:
        candidate = Path(__file__).resolve().parents[5] / "fixtures"
        if candidate.exists():
            settings.fixtures_root = candidate

    return settings


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_settings_secret_from_backend(settings: Settings) -> str | None:
    backend = (settings.settings_secret_backend or "").strip()
    if not backend:
        return None
    normalized = backend.lower()

    identifier = settings.settings_secret_name or "settings-secret"
    request = SecretRequest(
        identifier=identifier,
        field=settings.settings_secret_field,
    )

    try:
        if normalized == "vault":
            adapter = build_secrets_adapter(
                backend,
                url=settings.secrets_vault_addr,
                token=settings.secrets_vault_token,
                namespace=settings.secrets_vault_namespace,
                mount_point=settings.secrets_vault_mount_point,
                default_field=settings.settings_secret_field,
                verify=settings.secrets_vault_verify,
            )
        elif normalized == "aws":
            adapter = build_secrets_adapter(
                backend,
                profile_name=settings.secrets_aws_profile,
                region_name=settings.secrets_aws_region,
                default_field=settings.settings_secret_field,
            )
        else:
            # For any other backend, attempt to build the adapter and let it raise ValueError if unsupported
            adapter = build_secrets_adapter(backend)
    except ValueError as exc:
        LOGGER.error(
            "Unsupported secrets backend configured: %s", exc
        )
        return None
    except Exception as exc:  # pragma: no cover - defensive logging path
        LOGGER.error(
            "Failed to configure a secrets backend: %s", exc
        )
        return None

    try:
        return adapter.get_secret(request)
    except SecretRetrievalError as exc:
        LOGGER.error(
            "Configured secrets backend failed to resolve '%s': %s",
            request.identifier,
            exc,
        )
        return None


@lru_cache
def get_settings_secret() -> str | None:
    """Return the resolved secret used for encrypting persisted settings."""

    settings = get_settings()
    secret = _resolve_settings_secret_from_backend(settings)
    if secret:
        return secret
    if settings.settings_secret_key:
        return settings.settings_secret_key
    return None


@lru_cache
def get_settings_cipher() -> Fernet | None:
    """Return a cached Fernet instance for encrypting persisted settings."""

    secret = get_settings_secret()
    if secret:
        return Fernet(_derive_fernet_key(secret))
    if allow_insecure_startup():
        fallback = "theoria-insecure-test-secret"
        LOGGER.warning(
            "SETTINGS_SECRET_KEY not configured; using insecure fallback for tests",
        )
        return Fernet(_derive_fernet_key(fallback))
    return None
