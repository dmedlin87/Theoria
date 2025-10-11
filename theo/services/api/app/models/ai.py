"""Pydantic schemas for AI endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Sequence

from pydantic import AliasChoices, Field, model_validator

from ..ai.rag import (
    CollaborationResponse,
    ComparativeAnalysisResponse,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGAnswer,
    RAGCitation,
    SermonPrepResponse,
    VerseCopilotResponse,
)
from ..models.export import ExportManifest
from ..models.search import HybridSearchFilters
from .base import APIModel


class RecorderMetadata(APIModel):
    """Optional metadata supplied by clients when recording trails."""

    user_id: str | None = None
    source: str | None = None


class LLMModelRequest(APIModel):
    name: str
    provider: str = Field(default="openai")
    model: str
    config: dict[str, object] = Field(default_factory=dict)
    pricing: dict[str, float] = Field(default_factory=dict)
    latency: dict[str, float] = Field(default_factory=dict)
    routing: dict[str, object] = Field(default_factory=dict)
    make_default: bool = False


class LLMSettingsResponse(APIModel):
    default_model: str | None
    models: list[dict[str, object]]


class LLMDefaultRequest(APIModel):
    name: str


class LLMModelUpdateRequest(APIModel):
    provider: str | None = None
    model: str | None = None
    config: dict[str, object] | None = None
    pricing: dict[str, float] | None = None
    latency: dict[str, float] | None = None
    routing: dict[str, object] | None = None
    make_default: bool | None = None


MAX_CHAT_MESSAGE_CONTENT_LENGTH = 8_000
CHAT_SESSION_TOTAL_CHAR_BUDGET = 32_000
CHAT_SESSION_MEMORY_CHAR_BUDGET = 4_000


class ChatSessionMessage(APIModel):
    role: Literal["user", "assistant", "system"]
    content: str


class IntentTagPayload(APIModel):
    intent: str
    stance: str | None = None
    confidence: float | None = None


class ChatSessionPreferences(APIModel):
    mode: str | None = None
    default_filters: HybridSearchFilters | None = None
    frequently_opened_panels: list[str] = Field(default_factory=list)


class ChatMemoryEntry(APIModel):
    question: str
    answer: str
    prompt: str | None = None
    answer_summary: str | None = None
    citations: list[RAGCitation] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ChatSessionRequest(APIModel):
    messages: Sequence[ChatSessionMessage]
    session_id: str | None = None
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))
    prompt: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    recorder_metadata: RecorderMetadata | None = None
    stance: str | None = None
    mode_id: str | None = None
    preferences: ChatSessionPreferences | None = None

    @model_validator(mode="after")
    def _enforce_message_lengths(self) -> "ChatSessionRequest":
        for message in self.messages:
            if message.role != "user":
                continue

            if len(message.content) > MAX_CHAT_MESSAGE_CONTENT_LENGTH:
                raise ValueError(
                    "Chat message content exceeds the maximum allowed length"
                )
        return self


class ChatSessionResponse(APIModel):
    session_id: str
    message: ChatSessionMessage
    answer: RAGAnswer
    intent_tags: list[IntentTagPayload] | None = None


class ChatSessionState(APIModel):
    session_id: str
    stance: str | None = None
    summary: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    preferences: ChatSessionPreferences | None = None
    memory: list[ChatMemoryEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_interaction_at: datetime


class GuardrailProfile(APIModel):
    slug: str
    label: str
    description: str | None = None


class GuardrailSettings(APIModel):
    theological_traditions: list[GuardrailProfile]
    topic_domains: list[GuardrailProfile]


class AIFeaturesResponse(APIModel):
    guardrails: GuardrailSettings


DEFAULT_GUARDRAIL_SETTINGS = GuardrailSettings(
    theological_traditions=[
        GuardrailProfile(
            slug="anglican",
            label="Anglican Communion",
            description="Voices shaped by the Book of Common Prayer and via media sensibilities.",
        ),
        GuardrailProfile(
            slug="baptist",
            label="Baptist",
            description="Free church perspectives emphasising believer's baptism and congregational polity.",
        ),
        GuardrailProfile(
            slug="catholic",
            label="Roman Catholic",
            description="Magisterial readings grounded in the Catechism and sacramental theology.",
        ),
        GuardrailProfile(
            slug="orthodox",
            label="Eastern Orthodox",
            description="Patristic insights steeped in conciliar theology and theosis.",
        ),
        GuardrailProfile(
            slug="reformed",
            label="Reformed",
            description="Confessional frameworks influenced by Calvin, the Westminster Standards, and covenant theology.",
        ),
        GuardrailProfile(
            slug="wesleyan",
            label="Wesleyan/Methodist",
            description="Holiness traditions balancing scripture, reason, tradition, and experience.",
        ),
    ],
    topic_domains=[
        GuardrailProfile(
            slug="christology",
            label="Christology",
            description="Passages and commentary exploring the person and work of Christ.",
        ),
        GuardrailProfile(
            slug="soteriology",
            label="Soteriology",
            description="Studies on salvation, atonement, and grace.",
        ),
        GuardrailProfile(
            slug="ecclesiology",
            label="Ecclesiology",
            description="Perspectives on the nature and mission of the church.",
        ),
        GuardrailProfile(
            slug="sacramental",
            label="Sacramental Theology",
            description="Analyses of sacramental practice and theology across traditions.",
        ),
        GuardrailProfile(
            slug="biblical-theology",
            label="Biblical Theology",
            description="Canonical themes tracing the storyline of scripture.",
        ),
        GuardrailProfile(
            slug="ethics",
            label="Christian Ethics",
            description="Moral theology engaging discipleship, justice, and formation.",
        ),
    ],
)


class ProviderSettingsRequest(APIModel):
    api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    extra_headers: dict[str, str] | None = None


class ProviderSettingsResponse(APIModel):
    provider: str
    base_url: str | None = None
    default_model: str | None = None
    extra_headers: dict[str, str] | None = None
    has_api_key: bool = False


class VerseCopilotRequest(APIModel):
    osis: str | None = None
    passage: str | None = None
    question: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))
    recorder_metadata: RecorderMetadata | None = None

    @model_validator(mode="after")
    def _validate_reference(self) -> "VerseCopilotRequest":
        if not (self.osis or self.passage):
            raise ValueError("Provide an OSIS reference or passage.")
        return self


class SermonPrepRequest(APIModel):
    topic: str
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))
    recorder_metadata: RecorderMetadata | None = None
    outline_template: list[str] | None = Field(
        default=None,
        description="Custom outline structure (e.g., ['Opening', 'Body', 'Closing']). Defaults to a four-part liturgical structure.",
    )
    key_points_limit: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum number of key points to extract from citations (1-10)",
    )


class ComparativeAnalysisRequest(APIModel):
    osis: str
    participants: Sequence[str]
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))


class MultimediaDigestRequest(APIModel):
    collection: str | None = None
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))


class DevotionalRequest(APIModel):
    osis: str
    focus: str = Field(default="reflection")
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))


class CollaborationRequest(APIModel):
    thread: str
    osis: str
    viewpoints: Sequence[str]
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))


class CorpusCurationRequest(APIModel):
    since: str | None = None


class TranscriptExportRequest(APIModel):
    document_id: str
    format: str = Field(default="markdown")


ExportPresetId = Literal[
    "sermon-markdown",
    "sermon-ndjson",
    "sermon-csv",
    "sermon-pdf",
    "transcript-markdown",
    "transcript-csv",
    "transcript-pdf",
]


class ExportDeliverableResponse(APIModel):
    """Serialized payload returned by the sermon and transcript export presets."""

    preset: ExportPresetId
    format: Literal["markdown", "ndjson", "csv", "pdf"]
    filename: str
    media_type: str
    content: str | bytes


class CitationExportRequest(APIModel):
    """Request payload for exporting citations used by the copilot."""

    citations: Sequence[RAGCitation]


class CitationExportResponse(APIModel):
    """Response describing the rendered citation export bundle."""

    manifest: ExportManifest
    records: list[dict[str, Any]]
    csl: list[dict[str, Any]]
    manager_payload: dict[str, Any]


class GuardrailSuggestion(APIModel):
    """Client-side action recommended when guardrails block a response."""

    action: Literal["search", "upload"] = Field(
        default="search",
        description="The type of UI action that should be rendered.",
    )
    label: str = Field(description="Short label to display on the action control.")
    description: str | None = Field(
        default=None,
        description="Optional helper text describing why this suggestion is useful.",
    )
    query: str | None = Field(
        default=None,
        description="Suggested natural-language query when pivoting into search.",
    )
    osis: str | None = Field(
        default=None,
        description="OSIS reference that should be pre-filled for follow-up exploration.",
    )
    filters: HybridSearchFilters | None = Field(
        default=None,
        description="Search filters aligned with the guardrail configuration that failed.",
    )
    collection: str | None = Field(
        default=None,
        description="Optional collection identifier when directing the user to upload data.",
    )


class GuardrailFailureMetadata(APIModel):
    """Structured metadata describing a guardrail refusal."""

    code: str = Field(description="Stable identifier for the guardrail condition.")
    guardrail: Literal["retrieval", "generation", "safety", "ingest", "unknown"] = Field(
        default="unknown",
        description="High-level guardrail category that blocked the response.",
    )
    suggested_action: Literal["search", "upload", "retry", "none"] = Field(
        default="search",
        description="Client hint describing the most helpful follow-up action.",
    )
    filters: HybridSearchFilters | None = Field(
        default=None,
        description="Resolved filters that contributed to the guardrail decision.",
    )
    safe_refusal: bool = Field(
        default=False,
        description="Indicates whether a fallback refusal message was considered safe to surface.",
    )
    reason: str | None = Field(
        default=None,
        description="Optional human-readable reason emitted by the guardrail subsystem.",
    )


class GuardrailAdvisory(APIModel):
    """Structured payload returned when guardrails refuse to answer."""

    message: str = Field(description="Human-readable explanation of the guardrail outcome.")
    suggestions: Sequence[GuardrailSuggestion] = Field(
        default_factory=list,
        description="Interactive follow-up actions that the client can surface.",
    )
    metadata: GuardrailFailureMetadata | None = Field(
        default=None,
        description="Machine-readable metadata about the guardrail failure.",
    )


AIResponse = (
    VerseCopilotResponse
    | SermonPrepResponse
    | ComparativeAnalysisResponse
    | MultimediaDigestResponse
    | DevotionalResponse
    | CollaborationResponse
)


__all__ = [
    "CollaborationRequest",
    "ComparativeAnalysisRequest",
    "DevotionalRequest",
    "ChatSessionMessage",
    "ChatSessionRequest",
    "ChatSessionResponse",
    "RecorderMetadata",
    "LLMModelRequest",
    "LLMModelUpdateRequest",
    "LLMSettingsResponse",
    "LLMDefaultRequest",
    "ProviderSettingsRequest",
    "ProviderSettingsResponse",
    "MultimediaDigestRequest",
    "SermonPrepRequest",
    "VerseCopilotRequest",
    "CorpusCurationRequest",
    "TranscriptExportRequest",
    "ExportDeliverableResponse",
    "ExportPresetId",
    "CitationExportRequest",
    "CitationExportResponse",
    "AIResponse",
    "GuardrailProfile",
    "GuardrailSettings",
    "AIFeaturesResponse",
    "DEFAULT_GUARDRAIL_SETTINGS",
    "GuardrailSuggestion",
    "GuardrailFailureMetadata",
    "GuardrailAdvisory",
]
