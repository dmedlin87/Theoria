"""Pydantic schemas describing guardrail catalogues and advisories."""

from __future__ import annotations

from typing import Literal, Sequence

from pydantic import Field

from theo.infrastructure.api.app.models.base import APIModel
from theo.infrastructure.api.app.models.search import HybridSearchFilters


class GuardrailProfile(APIModel):
    """Describes a selectable guardrail tradition or topic domain."""

    slug: str
    label: str
    description: str | None = None


class GuardrailSettings(APIModel):
    """Collection of guardrail catalogues exposed to clients."""

    theological_traditions: list[GuardrailProfile]
    topic_domains: list[GuardrailProfile]


class AIFeaturesResponse(APIModel):
    """API response wrapper exposing available guardrail catalogues."""

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


__all__ = [
    "AIFeaturesResponse",
    "DEFAULT_GUARDRAIL_SETTINGS",
    "GuardrailAdvisory",
    "GuardrailFailureMetadata",
    "GuardrailProfile",
    "GuardrailSettings",
    "GuardrailSuggestion",
]
