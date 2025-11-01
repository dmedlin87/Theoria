import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.ai.rag.guardrails import (
    GuardrailError,
    apply_guardrail_profile,
    guardrail_metadata,
    validate_model_completion,
    validate_model_completion_strict,
)
from theo.infrastructure.api.app.ai.rag.models import RAGCitation
from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchResult


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent.parent / "golden" / "rag"


def test_guardrail_metadata_matches_golden(
    golden_dir: Path, regression_factory
) -> None:
    citations = regression_factory.rag_citations(2)
    answer = regression_factory.rag_answer(citations=citations)

    metadata = guardrail_metadata(answer)

    golden_path = golden_dir / "guardrail_metadata_basic.json"
    assert golden_path.exists(), "Golden guardrail metadata file is missing"
    assert metadata == json.loads(golden_path.read_text())


# ============================================================================
# CITATION VALIDATION TESTS
# ============================================================================


@pytest.fixture
def sample_citations():
    """Create sample citations for testing."""
    return [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        ),
        RAGCitation(
            index=2,
            osis="Romans.8.28",
            anchor="t=120-180s",
            passage_id="2",
            document_id="doc2",
            document_title="Test Document 2",
            snippet="All things work together",
            source_url="/doc/doc2#passage-2",
        ),
        RAGCitation(
            index=3,
            osis="Psalm.23.1",
            anchor="page 45",
            passage_id="3",
            document_id="doc3",
            document_title="Test Document 3",
            snippet="The LORD is my shepherd",
            source_url="/doc/doc3#passage-3",
        ),
    ]


def test_citation_normalization_preserves_structure():
    """Test that citation normalization preserves OSIS structure while handling case/spacing."""
    citations = [
        RAGCitation(
            index=1,
            osis="1John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    completion = "Sources:\n[1] 1john.3.16 (Page 23)"
    result = validate_model_completion(completion, citations)
    assert result["status"] == "passed"
    assert result["cited_indices"] == [1]


def test_duplicate_citation_detection():
    """Test that duplicate citation indices are detected."""
    citations = [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    completion = "Sources:\n[1] John.3.16 (page 23)\n[1] John.3.16 (page 23)"
    result = validate_model_completion(completion, citations)
    assert result["status"] == "failed"
    assert "duplicate citation index 1" in result["decision_message"]
    assert result["validation_details"]["unique_cited"] == 1
    assert result["validation_details"]["min_required"] == 1


def test_minimum_coverage_with_multiple_citations(sample_citations):
    """Test minimum coverage requirements with multiple available citations."""
    # Only cite 1 out of 3 available (should require at least 1, so passes)
    completion = "Sources:\n[1] John.3.16 (page 23)"
    result = validate_model_completion(completion, sample_citations)
    assert result["status"] == "passed"  # 1 out of 3 passes (3//2 = 1)
    assert result["validation_details"]["unique_cited"] == 1
    assert result["validation_details"]["min_required"] == 1
    
    # Cite 2 out of 3 available (should pass)
    completion2 = "Sources:\n[1] John.3.16 (page 23)\n[2] Romans.8.28 (t=120-180s)"
    result2 = validate_model_completion(completion2, sample_citations)
    assert result2["status"] == "passed"
    assert result2["validation_details"]["unique_cited"] == 2
    assert result2["validation_details"]["min_required"] == 1
    
    # Test edge case: 4 citations available, should require 2 (50% of 4, max 3)
    four_citations = sample_citations + [
        RAGCitation(
            index=4,
            osis="Gen.1.1",
            anchor="page 1",
            passage_id="4",
            document_id="doc4",
            document_title="Test Document 4",
            snippet="In the beginning",
            source_url="/doc/doc4#passage-4",
        )
    ]
    # Only cite 1 out of 4 available (should fail, requires 2)
    completion3 = "Sources:\n[1] John.3.16 (page 23)"
    result3 = validate_model_completion(completion3, four_citations)
    assert result3["status"] == "failed"  # 1 out of 4 fails (4//2 = 2)
    assert "insufficient citation coverage" in result3["decision_message"]
    assert result3["validation_details"]["unique_cited"] == 1
    assert result3["validation_details"]["min_required"] == 2
    
    # Cite 2 out of 4 available (should pass)
    completion4 = "Sources:\n[1] John.3.16 (page 23)\n[2] Romans.8.28 (t=120-180s)"
    result4 = validate_model_completion(completion4, four_citations)
    assert result4["status"] == "passed"  # 2 out of 4 passes (meets requirement)
    assert result4["validation_details"]["unique_cited"] == 2
    assert result4["validation_details"]["min_required"] == 2


def test_minimum_coverage_with_single_citation():
    """Test that single citation scenarios work correctly."""
    citations = [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    completion = "Sources:\n[1] John.3.16 (page 23)"
    result = validate_model_completion(completion, citations)
    assert result["status"] == "passed"
    assert result["validation_details"]["unique_cited"] == 1
    assert result["validation_details"]["min_required"] == 1


def test_extra_content_after_sources_detection():
    """Test detection of extra content after Sources line."""
    citations = [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    # Should fail with extra content
    completion_with_extra = "Sources:\nExtra text here\n[1] John.3.16 (page 23)"
    result = validate_model_completion(completion_with_extra, citations)
    assert result["status"] == "failed"
    assert result["decision_reason"] == "extra_content_after_sources"
    
    # Should pass with proper content
    completion_proper = "Sources:\nHere are the sources:\n[1] John.3.16 (page 23)"
    result2 = validate_model_completion(completion_proper, citations)
    assert result2["status"] == "passed"


def test_validation_details_included_in_responses():
    """Test that validation details are included in all responses."""
    citations = [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    # Test successful completion
    completion = "Sources:\n[1] John.3.16 (page 23)"
    result = validate_model_completion(completion, citations)
    assert "validation_details" in result
    assert result["validation_details"]["unique_cited"] == 1
    assert result["validation_details"]["total_available"] == 1
    
    # Test failed completion
    completion_invalid = "Sources:\n[1] Romans.8.28 (page 23)"
    result2 = validate_model_completion(completion_invalid, citations)
    assert "validation_details" in result2
    assert "mismatches" in result2["validation_details"]


def test_strict_mode_includes_validation_details():
    """Test that strict mode includes validation details in GuardrailError metadata."""
    citations = [
        RAGCitation(
            index=1,
            osis="John.3.16",
            anchor="page 23",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="For God so loved the world",
            source_url="/doc/doc1#passage-1",
        )
    ]
    
    completion_with_duplicate = "Sources:\n[1] John.3.16 (page 23)\n[1] John.3.16 (page 23)"
    
    with pytest.raises(GuardrailError) as exc:
        validate_model_completion_strict(completion_with_duplicate, citations)
    
    assert "validation_details" in exc.value.metadata
    assert exc.value.metadata["validation_details"]["unique_cited"] == 1


# ============================================================================
# PROFILE FILTERING TELEMETRY TESTS
# ============================================================================


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing."""
    return [
        HybridSearchResult(
            id="1",
            document_id="doc1",
            text="Reformed theology passage",
            raw_text="Reformed theology passage",
            osis_ref="John.3.16",
            snippet="Reformed theology",
            rank=1,
            meta={"theological_tradition": "reformed", "topic_domain": "soteriology"},
        ),
        HybridSearchResult(
            id="2",
            document_id="doc2",
            text="Lutheran theology passage",
            raw_text="Lutheran theology passage",
            osis_ref="Romans.3.28",
            snippet="Lutheran theology",
            rank=2,
            meta={"theological_tradition": "lutheran", "topic_domain": "justification"},
        ),
        HybridSearchResult(
            id="3",
            document_id="doc3",
            text="Passage without metadata",
            raw_text="Passage without metadata",
            osis_ref="Psalm.23.1",
            snippet="No metadata",
            rank=3,
            meta=None,
        ),
    ]


def test_profile_filtering_telemetry_success(caplog, sample_search_results):
    """Test that successful profile filtering generates appropriate telemetry."""
    filters = HybridSearchFilters(
        theological_tradition="reformed",
        topic_domain="soteriology"
    )
    
    with caplog.at_level("INFO"):
        filtered, profile = apply_guardrail_profile(sample_search_results, filters)
    
    # Should have 3 info logs: start, completed, success
    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    assert len(info_records) == 3
    
    # Check start log - extra data is stored as attributes on the record
    start_log = info_records[0]
    assert "guardrail profile filtering started" in start_log.message
    assert hasattr(start_log, 'total_results')
    assert start_log.total_results == 3
    assert hasattr(start_log, 'tradition_filter')
    assert start_log.tradition_filter == "reformed"
    assert hasattr(start_log, 'domain_filter')
    assert start_log.domain_filter == "soteriology"
    assert hasattr(start_log, 'passage_ids_sample')
    assert len(start_log.passage_ids_sample) <= 3
    assert hasattr(start_log, 'total_passage_count')
    assert start_log.total_passage_count == 3
    
    # Check completed log
    completed_log = info_records[1]
    assert "guardrail profile filtering completed" in completed_log.message
    assert hasattr(completed_log, 'matched_count')
    assert completed_log.matched_count == 1
    assert hasattr(completed_log, 'remainder_count')
    assert completed_log.remainder_count == 2
    assert hasattr(completed_log, 'match_percentage')
    assert completed_log.match_percentage == pytest.approx(33.3, abs=0.1)
    assert hasattr(completed_log, 'missing_metadata_count')
    assert completed_log.missing_metadata_count == 1
    assert hasattr(completed_log, 'tradition_mismatch_count')
    assert completed_log.tradition_mismatch_count == 1
    assert hasattr(completed_log, 'domain_mismatch_count')
    assert completed_log.domain_mismatch_count == 1
    
    # Check success log
    success_log = info_records[2]
    assert "guardrail profile filtering successful" in success_log.message
    assert hasattr(success_log, 'matched_count')
    assert success_log.matched_count == 1
    
    # Verify filtering worked correctly
    assert len(filtered) == 3  # matched + remainder
    assert filtered[0].id == "1"  # matched result first
    assert profile == {"theological_tradition": "reformed", "topic_domain": "soteriology"}


def test_citation_normalization_numeric_prefixes():
    """Test OSIS normalization with numeric prefixes like 2Cor.3.18."""
    citations = [
        RAGCitation(
            index=1,
            osis="2Cor.3.18",
            anchor="page 45",
            passage_id="1",
            document_id="doc1",
            document_title="Test Document",
            snippet="But we all, with unveiled face",
            source_url="/doc/doc1#passage-1",
        ),
        RAGCitation(
            index=2,
            osis="1Tim.2.5",
            anchor="page 67",
            passage_id="2",
            document_id="doc2",
            document_title="Test Document 2",
            snippet="For there is one God",
            source_url="/doc/doc2#passage-2",
        ),
    ]
    
    completion = "Sources:\n[1] 2cor.3.18 (Page 45)\n[2] 1tim.2.5 (page 67)"
    result = validate_model_completion(completion, citations)
    assert result["status"] == "passed"
    assert result["cited_indices"] == [1, 2]


def test_profile_filtering_telemetry_no_matches(caplog, sample_search_results):
    """Test telemetry when no passages match the profile."""
    filters = HybridSearchFilters(
        theological_tradition="nonexistent",
        topic_domain="nonexistent"
    )
    
    with caplog.at_level("INFO"):
        with pytest.raises(GuardrailError) as exc:
            apply_guardrail_profile(sample_search_results, filters)
    
    # Should have 2 info logs: start, completed + 1 warning log
    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(info_records) == 2
    assert len(warning_records) == 1
    
    # Check warning log
    warning_log = warning_records[0]
    assert "no matches found" in warning_log.message
    assert hasattr(warning_log, 'matched_count')
    assert warning_log.matched_count == 0
    assert hasattr(warning_log, 'match_percentage')
    assert warning_log.match_percentage == 0.0
    assert hasattr(warning_log, 'missing_metadata_count')
    assert warning_log.missing_metadata_count == 1
    assert hasattr(warning_log, 'passage_ids_sample')
    assert len(warning_log.passage_ids_sample) <= 3
    
    # Check GuardrailError metadata
    assert exc.value.metadata["total_results"] == 3
    assert exc.value.metadata["matched_count"] == 0
    assert exc.value.metadata["missing_metadata_count"] == 1
    assert exc.value.metadata["tradition_mismatch_count"] == 2
    assert exc.value.metadata["domain_mismatch_count"] == 2


def test_profile_filtering_telemetry_bypass_cases(caplog, sample_search_results):
    """Test telemetry for bypass cases (no filters, invalid values)."""
    # Test no filters
    with caplog.at_level("DEBUG"):
        filtered, profile = apply_guardrail_profile(sample_search_results, None)
    
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    bypass_log = next(r for r in debug_records if "no filters provided" in r.message)
    assert hasattr(bypass_log, 'total_results')
    assert bypass_log.total_results == 3
    assert hasattr(bypass_log, 'filters_applied')
    assert bypass_log.filters_applied is False
    assert filtered == sample_search_results
    assert profile is None
    
    caplog.clear()
    
    # Test invalid filter values
    filters = HybridSearchFilters(theological_tradition="", topic_domain=None)
    with caplog.at_level("DEBUG"):
        filtered, profile = apply_guardrail_profile(sample_search_results, filters)
    
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    bypass_log = next(r for r in debug_records if "no valid filter values" in r.message)
    assert hasattr(bypass_log, 'total_results')
    assert bypass_log.total_results == 3
    assert hasattr(bypass_log, 'filters_applied')
    assert bypass_log.filters_applied is False
    assert filtered == sample_search_results
    assert profile is None


def test_profile_filtering_detailed_debug_logging(caplog, sample_search_results):
    """Test that detailed passage ID logging works at debug level."""
    filters = HybridSearchFilters(theological_tradition="reformed")
    
    with caplog.at_level("DEBUG"):
        filtered, profile = apply_guardrail_profile(sample_search_results, filters)
    
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    detailed_log = next(r for r in debug_records if "detailed results" in r.message)
    assert hasattr(detailed_log, 'matched_passage_ids')
    assert hasattr(detailed_log, 'remainder_passage_ids')
    assert detailed_log.matched_passage_ids == ["1"]
    assert set(detailed_log.remainder_passage_ids) == {"2", "3"}
