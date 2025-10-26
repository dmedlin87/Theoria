import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from theo.application.facades.database import Base
from theo.services.api.app.ingest.pipeline import run_pipeline_for_audio
from theo.services.api.app.ingest.stages.fetchers import AudioSourceFetcher
from theo.services.api.app.ingest.stages.parsers import AudioTranscriptionParser
from theo.services.api.app.ingest.stages.persisters import AudioDocumentPersister

@pytest.fixture
def sample_audio_path(tmp_path):
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio data")
    return audio_file


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

@patch.object(AudioSourceFetcher, 'fetch')
@patch.object(AudioTranscriptionParser, 'parse')
@patch.object(AudioDocumentPersister, 'persist')
def test_audio_pipeline_full(mock_persist, mock_parse, mock_fetch, sample_audio_path, db_session):
    """Test full audio pipeline from ingestion to persistence."""
    # Setup mock returns
    mock_fetch.return_value = {
        "audio_path": sample_audio_path,
        "sha256": "fake_sha256",
        "frontmatter": {"title": "Test Audio"},
        "audio_metadata": {"duration": 300, "format": "mp3"}
    }
    
    mock_parse.return_value = {
        "parser_result": {"chunks": [{"text": "Sample transcript", "timestamp": 0}]},
        "verse_anchors": [{"verse": "Jas 2:17", "confidence": 0.95}],
        "transcript_segments": [{"start": 0, "end": 10, "text": "Sample"}]
    }
    
    mock_persist.return_value = MagicMock(id="doc_123")
    
    # Run pipeline
    document = run_pipeline_for_audio(
        session=db_session,
        audio_path=sample_audio_path,
        source_type="ai_generated",
        frontmatter={"agents": ["Theologian", "Historian"]}
    )
    
    # Verify results
    assert document.id == "doc_123"
    mock_fetch.assert_called_once()
    mock_parse.assert_called_once()
    mock_persist.assert_called_once()

@patch("theo.services.api.app.ingest.stages.parsers.WhisperModel", autospec=True)
def test_transcription_quality(mock_whisper, sample_audio_path):
    """Test transcription quality with different audio qualities."""
    # Setup mock Whisper model
    mock_model = mock_whisper.return_value
    mock_model.transcribe.return_value = {"segments": [{"text": "Clear audio transcript"}]}
    
    # Test with good quality audio
    parser = AudioTranscriptionParser()
    segments = parser._transcribe_audio(sample_audio_path, MagicMock())
    assert "Clear audio transcript" in segments[0]["text"]
    
    # Test with background noise
    mock_model.transcribe.return_value = {"segments": [{"text": "[Background noise] Muffled speech"}]}
    segments = parser._transcribe_audio(sample_audio_path, MagicMock())
    assert "Muffled speech" in segments[0]["text"]

@patch("theo.services.api.app.ingest.stages.parsers.VerseDetector", autospec=True)
def test_verse_detection(mock_detector, sample_audio_path):
    """Test verse detection in transcribed text."""
    # Setup mock detector
    mock_detector.return_value.detect.return_value = [
        {"verse": "Jas 2:14-26", "confidence": 0.92}
    ]
    
    segments = [
        {"start": 0, "end": 30, "text": "Faith without works is dead as in James 2:17"}
    ]
    
    parser = AudioTranscriptionParser()
    anchors = parser._detect_scripture_references(segments, MagicMock())
    
    assert anchors[0]["verse"] == "Jas 2:14-26"
    assert anchors[0]["confidence"] > 0.9
