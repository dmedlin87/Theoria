from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .base import APIModel, Passage


class DocumentStatus(str):
    RECEIVED = "received"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(APIModel):
    document_id: UUID = Field(default_factory=uuid4)
    title: str | None = None
    source_type: str
    status: str = DocumentStatus.RECEIVED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] | None = None


class DocumentIngestResponse(APIModel):
    document_id: UUID
    status: str


class DocumentDetailResponse(Document):
    passages: list[Passage] = []
