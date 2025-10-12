"""Tests covering the research run envelope schema."""

import pytest
from pydantic import ValidationError

from mcp_server import schemas


def _sample_evidence_card() -> schemas.EvidenceCardArtifact:
    return schemas.EvidenceCardArtifact(
        id="card-1",
        claim="Paul's Areopagus speech emphasizes repentance",
        citations=[
            schemas.EvidenceCardCitation(
                title="Acts of the Apostles",
                url="https://example.com/acts",
                source_type="primary",
                accessed="2025-01-01",
                excerpt="They received the word with all readiness of mind.",
            )
        ],
        evidence_points=[
            "Acts 17:30 records Paul's universal call to repentance.",
        ],
        counter_evidence=[],
        stability=schemas.EvidenceCardStability(
            score=0.82,
            components=schemas.EvidenceCardStabilityComponents(
                attestation=0.9,
                consensus=0.75,
                recency_risk=0.1,
                textual_variants=0.05,
            ),
        ),
        confidence=0.78,
        open_questions=[
            "How does Luke's portrayal compare with Pauline epistles?",
        ],
        rubric_version="2025-10-12",
        schema_version="2025-10-12",
    )


def test_research_run_envelope_round_trip() -> None:
    """The research run envelope should accept the canonical sample payload."""

    envelope = schemas.ResearchRunEnvelope(
        run_meta=schemas.ResearchRunMeta(
            app="Theoria",
            app_alias=["TheoEngine"],
            rubric_version="2025-10-12",
            schema_version="2025-10-12",
            model_final="gpt-5",
            models_used=["gpt-5-mini", "gpt-5"],
            file_ids_used=["file-1", "file-2"],
            web_used=True,
            started_at="2025-01-01T12:00:00Z",
            completed_at="2025-01-01T12:05:00Z",
        ),
        artifacts=[_sample_evidence_card()],
        run_logs=schemas.RunLogs(
            tools=[{"name": "web_search", "status": "ok"}],
            compromises=[],
            warnings=["Search results limited to cached sources."],
            notes=["Follow up with o3-deep-research for broader survey."],
        ),
    )

    dumped = envelope.model_dump()
    assert dumped["run_meta"]["app"] == "Theoria"
    assert dumped["artifacts"][0]["stability"]["score"] == pytest.approx(0.82)
    assert dumped["run_logs"]["tools"][0]["name"] == "web_search"
    assert dumped["validation_errors"] == []


def test_evidence_card_enforces_score_bounds() -> None:
    """Evidence card stability score must remain within the configured range."""

    with pytest.raises(ValidationError):
        schemas.EvidenceCardArtifact(
            id="card-2",
            claim="Invalid score example",
            stability=schemas.EvidenceCardStability(
                score=1.5,
            ),
            confidence=0.5,
            rubric_version="2025-10-12",
            schema_version="2025-10-12",
        )
