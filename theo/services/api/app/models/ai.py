"""Pydantic schemas for AI endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Sequence

from pydantic import Field, model_validator

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
from ..models.research_plan import ResearchPlan
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


REASONING_MODE_IDS = {
    "detective",
    "critic",
    "apologist",
    "synthesizer",
}


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
    intent_tags: list[IntentTagPayload] | None = None
    answer_summary: str | None = None
    citations: list[RAGCitation] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    goal_id: str | None = None
    trail_id: str | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None
    topics: list[str] | None = None
    entities: list[str] | None = None
    goal_ids: list[str] | None = None
    source_types: list[str] | None = None
    sentiment: str | None = None
    created_at: datetime
    trail_id: str | None = None
    digest_hash: str | None = None
    key_entities: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ChatGoalState(APIModel):
    id: str
    title: str
    trail_id: str
    status: Literal["active", "closed"] = "active"
    priority: int = 0
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
    last_interaction_at: datetime


class ChatGoalProgress(APIModel):
    goals: list[ChatGoalState] = Field(default_factory=list)


class GoalPriorityUpdateRequest(APIModel):
    priority: int


class GoalCloseRequest(APIModel):
    summary: str | None = None


class ModeAliasMixin:
    """Mixin translating deprecated ``mode`` payloads to the ``model`` field."""

    @model_validator(mode="before")
    @classmethod
    def _promote_mode_alias(cls, data: object) -> object:
        if isinstance(data, dict) and "model" not in data and "mode" in data:
            promoted = dict(data)
            promoted["model"] = promoted.pop("mode")
            return promoted
        return data


class ChatSessionRequest(ModeAliasMixin, APIModel):
    messages: Sequence[ChatSessionMessage]
    session_id: str | None = None
    model: str | None = None
    prompt: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    recorder_metadata: RecorderMetadata | None = None
    stance: str | None = None
    mode_id: str | None = None
    preferences: ChatSessionPreferences | None = None

    @model_validator(mode="after")
    def _validate_reasoning_mode(self) -> "ChatSessionRequest":
        if self.mode_id and self.mode_id not in REASONING_MODE_IDS:
            raise ValueError(f"Unknown reasoning mode id '{self.mode_id}'")
        return self

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
    plan: ResearchPlan | None = None


class ChatSessionState(APIModel):
    session_id: str
    stance: str | None = None
    summary: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    preferences: ChatSessionPreferences | None = None
    memory: list[ChatMemoryEntry] = Field(default_factory=list)
    goals: list[ChatGoalState] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_interaction_at: datetime
    plan: ResearchPlan | None = None


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


class VerseCopilotRequest(ModeAliasMixin, APIModel):
    osis: str | None = None
    passage: str | None = Field(None, max_length=200)
    question: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    model: str | None = None
    recorder_metadata: RecorderMetadata | None = None

    @model_validator(mode="after")
    def _validate_reference(self) -> "VerseCopilotRequest":
        if not (self.osis or self.passage):
            raise ValueError("Provide an OSIS reference or passage.")
        return self


class SermonPrepRequest(ModeAliasMixin, APIModel):
    topic: str
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    model: str | None = None
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


class ComparativeAnalysisRequest(ModeAliasMixin, APIModel):
    osis: str
    participants: Sequence[str]
    model: str | None = None


class MultimediaDigestRequest(ModeAliasMixin, APIModel):
    collection: str | None = None
    model: str | None = None


class DevotionalRequest(ModeAliasMixin, APIModel):
    osis: str
    focus: str = Field(default="reflection")
    model: str | None = None


class CollaborationRequest(ModeAliasMixin, APIModel):
    thread: str
    osis: str
    viewpoints: Sequence[str]
    model: str | None = None


class CorpusCurationRequest(APIModel):
    since: str | None = None


class TranscriptExportRequest(APIModel):
    document_id: str
    format: str = Field(default="markdown")


class PerspectiveCitationModel(APIModel):
    """Citation payload surfaced for each perspective run."""

    document_id: str | None = None
    document_title: str | None = None
    osis: str | None = None
    snippet: str
    rank: int | None = None
    score: float | None = None


class PerspectiveViewModel(APIModel):
    """Structured answer for a single theological perspective."""

    perspective: Literal["skeptical", "apologetic", "neutral"]
    answer: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    key_claims: list[str] = Field(default_factory=list)
    citations: list[PerspectiveCitationModel] = Field(default_factory=list)


class PerspectiveSynthesisRequest(APIModel):
    """Request payload for the multi-perspective synthesis workflow."""

    question: str
    filters: HybridSearchFilters | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PerspectiveSynthesisResponse(APIModel):
    """Response exposing consensus and tensions across perspectives."""

    question: str
    consensus_points: list[str] = Field(default_factory=list)
    tension_map: dict[str, list[str]] = Field(default_factory=dict)
    meta_analysis: str
    perspective_views: dict[str, PerspectiveViewModel] = Field(default_factory=dict)


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


class LoopControlAction(str, Enum):
    """Enumerates control surface actions available to the research loop."""

    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    STEP = "step"


class ResearchLoopStatus(str, Enum):
    """Describes the lifecycle state of the Cognitive Scholar research loop."""

    IDLE = "idle"
    RUNNING = "running"
    STEPPING = "stepping"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class ResearchLoopState(APIModel):
    """Persisted state snapshot for the research loop controller."""

    session_id: str
    status: ResearchLoopStatus = ResearchLoopStatus.IDLE
    current_step_index: int = 0
    total_steps: int = 0
    pending_actions: list[str] = Field(default_factory=list)
    partial_answer: str | None = None
    last_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


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
    "PerspectiveCitationModel",
    "PerspectiveViewModel",
    "PerspectiveSynthesisRequest",
    "PerspectiveSynthesisResponse",
    "AIResponse",
    "GuardrailProfile",
    "GuardrailSettings",
    "AIFeaturesResponse",
    "DEFAULT_GUARDRAIL_SETTINGS",
    "GuardrailSuggestion",
    "GuardrailFailureMetadata",
    "GuardrailAdvisory",
    "LoopControlAction",
    "ResearchLoopStatus",
    "ResearchLoopState",
]
