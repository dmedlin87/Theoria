"""Pydantic schemas for notebook collaboration endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from .base import APIModel, BaseModel


NotebookRole = Literal["owner", "editor", "viewer"]


class NotebookCollaboratorPayload(BaseModel):
    subject: str = Field(min_length=1)
    role: NotebookRole = Field(default="viewer")


class NotebookCollaboratorResponse(APIModel):
    id: str
    subject: str
    role: NotebookRole
    created_at: datetime


class EntryMentionPayload(BaseModel):
    osis_ref: str = Field(min_length=1)
    document_id: str | None = Field(default=None)
    context: str | None = Field(default=None, max_length=10_000)


class EntryMentionResponse(APIModel):
    id: str
    osis_ref: str
    document_id: str | None = None
    context: str | None = None
    created_at: datetime


class NotebookEntryCreate(BaseModel):
    content: str = Field(min_length=1)
    document_id: str | None = Field(default=None)
    osis_ref: str | None = Field(default=None)
    mentions: list[EntryMentionPayload] | None = Field(default=None)


class NotebookEntryUpdate(BaseModel):
    content: str | None = Field(default=None)
    osis_ref: str | None = Field(default=None)
    mentions: list[EntryMentionPayload] | None = Field(default=None)


class NotebookEntryResponse(APIModel):
    id: str
    notebook_id: str
    document_id: str | None = None
    osis_ref: str | None = None
    content: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    mentions: list[EntryMentionResponse]


class NotebookCreatePayload(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = Field(default=None)
    team_id: str | None = Field(default=None)
    is_public: bool = Field(default=False)
    collaborators: list[NotebookCollaboratorPayload] | None = Field(default=None)


class NotebookUpdatePayload(BaseModel):
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)
    is_public: bool | None = Field(default=None)
    collaborators: list[NotebookCollaboratorPayload] | None = Field(default=None)


class NotebookResponse(APIModel):
    id: str
    title: str
    description: str | None = None
    team_id: str | None = None
    is_public: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    primary_osis: str | None = None
    entry_count: int
    entries: list[NotebookEntryResponse]
    collaborators: list[NotebookCollaboratorResponse]


class NotebookListResponse(APIModel):
    notebooks: list[NotebookResponse]


class NotebookEntryCreated(APIModel):
    id: str
    notebook_id: str
    created_at: datetime
    updated_at: datetime


class NotebookRealtimeSnapshot(APIModel):
    model_config = ConfigDict(extra="allow")

    notebook_id: str
    version: int
    updated_at: datetime


__all__ = [
    "EntryMentionPayload",
    "EntryMentionResponse",
    "NotebookCollaboratorPayload",
    "NotebookCollaboratorResponse",
    "NotebookCreatePayload",
    "NotebookEntryCreate",
    "NotebookEntryCreated",
    "NotebookEntryResponse",
    "NotebookEntryUpdate",
    "NotebookListResponse",
    "NotebookRealtimeSnapshot",
    "NotebookResponse",
    "NotebookRole",
    "NotebookUpdatePayload",
]
