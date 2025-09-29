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


class ChatSessionMessage(APIModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatSessionRequest(APIModel):
    messages: Sequence[ChatSessionMessage]
    session_id: str | None = None
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "mode"))
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    recorder_metadata: RecorderMetadata | None = None
    stance: str | None = None
    mode_id: str | None = None
    frequently_opened_panels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_message_lengths(self) -> "ChatSessionRequest":
        for message in self.messages:
            if message.role != "user":
                continue

            if len(message.content) > MAX_CHAT_MESSAGE_CONTENT_LENGTH:
                raise ValueError(
                    "Chat message content exceeds the maximum allowed length"
                )
        if self.frequently_opened_panels:
            unique: list[str] = []
            seen: set[str] = set()
            for panel in self.frequently_opened_panels:
                if not isinstance(panel, str):
                    continue
                trimmed = panel.strip()
                if not trimmed or trimmed in seen:
                    continue
                seen.add(trimmed)
                unique.append(trimmed)
            object.__setattr__(self, "frequently_opened_panels", unique)
        return self


class ChatSessionResponse(APIModel):
    session_id: str
    message: ChatSessionMessage
    answer: RAGAnswer


class ChatSessionMemory(APIModel):
    summary: str | None = None
    snippets: list[str] = Field(default_factory=list)


class ChatSessionPreferences(APIModel):
    mode_id: str | None = Field(default=None, serialization_alias="modeId")
    default_filters: HybridSearchFilters | None = Field(
        default=None, serialization_alias="defaultFilters"
    )
    frequently_opened_panels: list[str] = Field(
        default_factory=list, serialization_alias="frequentlyOpenedPanels"
    )


class ChatSessionTranscriptMessage(ChatSessionMessage):
    id: str
    citations: list[RAGCitation] = Field(default_factory=list)
    created_at: datetime | None = None


class ChatSessionDetailResponse(APIModel):
    session_id: str
    stance: str | None = None
    mode_id: str | None = None
    summary: str | None = None
    memory: ChatSessionMemory = Field(default_factory=ChatSessionMemory)
    preferences: ChatSessionPreferences = Field(default_factory=ChatSessionPreferences)
    messages: list[ChatSessionTranscriptMessage] = Field(default_factory=list)
    linked_document_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


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
    "ChatSessionDetailResponse",
    "ChatSessionMemory",
    "ChatSessionPreferences",
    "ChatSessionTranscriptMessage",
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
]
