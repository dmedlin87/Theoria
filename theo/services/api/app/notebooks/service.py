"""Service helpers implementing notebook CRUD and collaboration rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import (
    Document,
    EntryMention,
    Notebook,
    NotebookCollaborator,
    NotebookCollaboratorRole,
    NotebookEntry,
)

from ..ingest.osis import expand_osis_reference
from ..models.notebooks import (
    EntryMentionPayload,
    NotebookCollaboratorPayload,
    NotebookCreatePayload,
    NotebookEntryCreate,
    NotebookEntryResponse,
    NotebookEntryUpdate,
    NotebookListResponse,
    NotebookResponse,
    NotebookUpdatePayload,
)
from ..routes.realtime import publish_notebook_update
from ..security import Principal


def _principal_subject(principal: Principal | None) -> str | None:
    if not principal:
        return None
    subject = principal.get("subject")
    if subject:
        return str(subject)
    token = principal.get("token")
    return str(token) if token else None


def _principal_teams(principal: Principal | None) -> set[str]:
    if not principal:
        return set()
    claims = principal.get("claims") or {}
    teams_claim = claims.get("teams") or claims.get("team_ids") or []
    if isinstance(teams_claim, str):
        teams: Iterable[Any] = [teams_claim]
    elif isinstance(teams_claim, Iterable):
        teams = teams_claim
    else:
        teams = [teams_claim]
    normalized: set[str] = set()
    for item in teams:
        if item:
            normalized.add(str(item))
    team = claims.get("team")
    if team:
        normalized.add(str(team))
    return normalized


def _validate_osis_reference(reference: str | None) -> str | None:
    if reference is None:
        return None
    candidate = reference.strip()
    if not candidate:
        return None
    verses = expand_osis_reference(candidate)
    if not verses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OSIS reference: {candidate}",
        )
    return candidate


def _assert_document_exists(session: Session, document_id: str) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


def _serialize_mention(mention: EntryMention) -> dict[str, Any]:
    return {
        "id": mention.id,
        "osis_ref": mention.osis_ref,
        "document_id": mention.document_id,
        "context": mention.context,
        "created_at": mention.created_at,
    }


def _serialize_entry(entry: NotebookEntry) -> NotebookEntryResponse:
    return NotebookEntryResponse(
        id=entry.id,
        notebook_id=entry.notebook_id,
        document_id=entry.document_id,
        osis_ref=entry.osis_ref,
        content=entry.content,
        created_by=entry.created_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        mentions=[EntryMentionResponse.model_validate(_serialize_mention(m)) for m in entry.mentions],
    )


from ..models.notebooks import EntryMentionResponse, NotebookCollaboratorResponse


def _serialize_collaborator(collaborator: NotebookCollaborator) -> NotebookCollaboratorResponse:
    return NotebookCollaboratorResponse(
        id=collaborator.id,
        subject=collaborator.subject,
        role=collaborator.role.value,
        created_at=collaborator.created_at,
    )


def _primary_osis(entry_iter: Iterable[NotebookEntry]) -> str | None:
    for entry in entry_iter:
        if entry.osis_ref:
            return entry.osis_ref
        for mention in entry.mentions:
            if mention.osis_ref:
                return mention.osis_ref
    return None


def _serialize_notebook(notebook: Notebook) -> NotebookResponse:
    entries = [_serialize_entry(entry) for entry in notebook.entries]
    collaborators = [
        _serialize_collaborator(collaborator) for collaborator in notebook.collaborators
    ]
    return NotebookResponse(
        id=notebook.id,
        title=notebook.title,
        description=notebook.description,
        team_id=notebook.team_id,
        is_public=notebook.is_public,
        created_by=notebook.created_by,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
        primary_osis=_primary_osis(notebook.entries),
        entry_count=len(entries),
        entries=entries,
        collaborators=collaborators,
    )


def _ensure_team_membership(principal: Principal | None, team_id: str) -> None:
    if not team_id:
        return
    teams = _principal_teams(principal)
    if team_id not in teams:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Principal is not a member of the requested team",
        )


def _has_edit_access(notebook: Notebook, principal: Principal | None) -> bool:
    subject = _principal_subject(principal)
    if subject and subject == notebook.created_by:
        return True
    teams = _principal_teams(principal)
    if notebook.team_id and notebook.team_id in teams:
        return True
    if subject:
        for collaborator in notebook.collaborators:
            if collaborator.subject == subject and collaborator.role in (
                NotebookCollaboratorRole.OWNER,
                NotebookCollaboratorRole.EDITOR,
            ):
                return True
    return False


def _has_read_access(notebook: Notebook, principal: Principal | None) -> bool:
    if notebook.is_public:
        return True
    subject = _principal_subject(principal)
    if subject and subject == notebook.created_by:
        return True
    teams = _principal_teams(principal)
    if notebook.team_id and notebook.team_id in teams:
        return True
    if subject:
        return any(collaborator.subject == subject for collaborator in notebook.collaborators)
    return False


class NotebookService:
    """Business logic for managing notebooks."""

    def __init__(self, session: Session, principal: Principal | None):
        self.session = session
        self.principal = principal

    # ------------------------------------------------------------------
    # Notebooks
    # ------------------------------------------------------------------

    def list_notebooks(self) -> NotebookListResponse:
        subject = _principal_subject(self.principal)
        teams = _principal_teams(self.principal)
        visibility_clauses = [
            Notebook.is_public.is_(True),
            Notebook.created_by == subject,
            and_(Notebook.team_id.is_not(None), Notebook.team_id.in_(teams)),
        ]
        if subject:
            visibility_clauses.append(NotebookCollaborator.subject == subject)

        stmt = (
            select(Notebook)
            .outerjoin(NotebookCollaborator)
            .where(or_(*visibility_clauses))
            .order_by(Notebook.updated_at.desc())
        )
        notebooks = self.session.execute(stmt).scalars().unique().all()
        return NotebookListResponse(notebooks=[_serialize_notebook(nb) for nb in notebooks])

    def create_notebook(self, payload: NotebookCreatePayload) -> NotebookResponse:
        subject = _principal_subject(self.principal)
        if not subject:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing principal")
        if payload.team_id:
            _ensure_team_membership(self.principal, payload.team_id)

        notebook = Notebook(
            title=payload.title,
            description=payload.description,
            team_id=payload.team_id,
            is_public=payload.is_public,
            created_by=subject,
        )
        self.session.add(notebook)
        self.session.flush()

        collaborators_payload = payload.collaborators or []
        collaborators: list[NotebookCollaborator] = []
        seen_subjects = {subject}
        for collaborator_payload in collaborators_payload:
            normalized_subject = collaborator_payload.subject.strip()
            if not normalized_subject or normalized_subject in seen_subjects:
                continue
            role = NotebookCollaboratorRole(collaborator_payload.role)
            collaborator = NotebookCollaborator(
                notebook_id=notebook.id,
                subject=normalized_subject,
                role=role,
            )
            collaborators.append(collaborator)
            seen_subjects.add(normalized_subject)
        self.session.add_all(collaborators)
        self.session.commit()
        self.session.refresh(notebook)
        publish_notebook_update(notebook.id, {
            "action": "created",
            "notebook_id": notebook.id,
            "updated_at": notebook.updated_at,
        })
        return _serialize_notebook(notebook)

    def get_notebook(self, notebook_id: str) -> NotebookResponse:
        notebook = self.session.get(Notebook, notebook_id)
        if notebook is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
        if not _has_read_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return _serialize_notebook(notebook)

    def update_notebook(self, notebook_id: str, payload: NotebookUpdatePayload) -> NotebookResponse:
        notebook = self.session.get(Notebook, notebook_id)
        if notebook is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
        if not _has_edit_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        if payload.title is not None:
            notebook.title = payload.title
        if payload.description is not None:
            notebook.description = payload.description
        if payload.is_public is not None:
            notebook.is_public = payload.is_public

        if payload.collaborators is not None:
            self._sync_collaborators(notebook, payload.collaborators)

        self.session.add(notebook)
        self.session.commit()
        self.session.refresh(notebook)
        publish_notebook_update(notebook.id, {
            "action": "updated",
            "notebook_id": notebook.id,
            "updated_at": notebook.updated_at,
        })
        return _serialize_notebook(notebook)

    def delete_notebook(self, notebook_id: str) -> None:
        notebook = self.session.get(Notebook, notebook_id)
        if notebook is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
        subject = _principal_subject(self.principal)
        if not subject or subject != notebook.created_by:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        self.session.delete(notebook)
        self.session.commit()
        publish_notebook_update(
            notebook_id,
            {
                "action": "deleted",
                "notebook_id": notebook_id,
                "updated_at": datetime.now(UTC),
            },
        )

    # ------------------------------------------------------------------
    # Entries
    # ------------------------------------------------------------------

    def create_entry(self, notebook_id: str, payload: NotebookEntryCreate) -> NotebookEntryResponse:
        notebook = self.session.get(Notebook, notebook_id)
        if notebook is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
        if not _has_edit_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        subject = _principal_subject(self.principal)
        if not subject:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing principal")

        osis_ref = _validate_osis_reference(payload.osis_ref)
        if payload.document_id:
            _assert_document_exists(self.session, payload.document_id)

        entry = NotebookEntry(
            notebook_id=notebook.id,
            document_id=payload.document_id,
            osis_ref=osis_ref,
            content=payload.content,
            created_by=subject,
        )
        self.session.add(entry)
        self.session.flush()

        mentions = self._build_mentions(entry, payload.mentions or [])
        if mentions:
            self.session.add_all(mentions)

        self.session.commit()
        self.session.refresh(entry)
        self.session.refresh(notebook)
        publish_notebook_update(notebook.id, {
            "action": "entry.created",
            "notebook_id": notebook.id,
            "entry_id": entry.id,
            "updated_at": notebook.updated_at,
        })
        return _serialize_entry(entry)

    def update_entry(self, entry_id: str, payload: NotebookEntryUpdate) -> NotebookEntryResponse:
        entry = self.session.get(NotebookEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
        notebook = entry.notebook
        if not _has_edit_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        if payload.content is not None:
            entry.content = payload.content
        if payload.osis_ref is not None:
            entry.osis_ref = _validate_osis_reference(payload.osis_ref)
        if payload.mentions is not None:
            for mention in list(entry.mentions):
                self.session.delete(mention)
            mentions = self._build_mentions(entry, payload.mentions)
            if mentions:
                self.session.add_all(mentions)

        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        publish_notebook_update(entry.notebook_id, {
            "action": "entry.updated",
            "notebook_id": entry.notebook_id,
            "entry_id": entry.id,
            "updated_at": entry.updated_at,
        })
        return _serialize_entry(entry)

    def delete_entry(self, entry_id: str) -> None:
        entry = self.session.get(NotebookEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
        notebook = entry.notebook
        if not _has_edit_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        notebook_id = entry.notebook_id
        self.session.delete(entry)
        self.session.commit()
        publish_notebook_update(
            notebook_id,
            {
                "action": "entry.deleted",
                "notebook_id": notebook_id,
                "entry_id": entry.id,
                "updated_at": datetime.now(UTC),
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_mentions(
        self, entry: NotebookEntry, mention_payloads: Iterable[EntryMentionPayload]
    ) -> list[EntryMention]:
        mentions: list[EntryMention] = []
        for payload in mention_payloads:
            osis_ref = _validate_osis_reference(payload.osis_ref)
            document_id = payload.document_id
            if document_id:
                _assert_document_exists(self.session, document_id)
            mention = EntryMention(
                entry_id=entry.id,
                osis_ref=osis_ref or "",
                document_id=document_id,
                context=payload.context,
            )
            mentions.append(mention)
        return mentions

    def _sync_collaborators(
        self, notebook: Notebook, collaborators: Iterable[NotebookCollaboratorPayload]
    ) -> None:
        existing = {collaborator.subject: collaborator for collaborator in notebook.collaborators}
        seen: set[str] = set()
        subject = _principal_subject(self.principal)
        for payload in collaborators:
            normalized = payload.subject.strip()
            if not normalized or normalized == subject:
                continue
            seen.add(normalized)
            role = NotebookCollaboratorRole(payload.role)
            record = existing.get(normalized)
            if record is None:
                record = NotebookCollaborator(
                    notebook_id=notebook.id,
                    subject=normalized,
                    role=role,
                )
                self.session.add(record)
            else:
                record.role = role

        for subject_key, record in existing.items():
            if subject_key not in seen:
                self.session.delete(record)

    # Convenience wrappers -------------------------------------------------

    def ensure_accessible(self, notebook_id: str) -> Notebook:
        notebook = self.session.get(Notebook, notebook_id)
        if notebook is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
        if not _has_read_access(notebook, self.principal):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return notebook


__all__ = ["NotebookService"]
