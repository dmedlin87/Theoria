from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class APIModel(BaseModel):
    """Base API schema with shared configuration."""

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda dt: dt.isoformat(), UUID: str}


class Passage(APIModel):
    id: UUID
    document_id: UUID
    osis_refs: list[str]
    text: str
    source_anchor: str | None = Field(default=None, description="Page or timestamp anchor")
    score: float | None = None
    metadata: dict[str, str] | None = None
