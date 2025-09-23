"""Document retrieval helpers."""

from uuid import UUID

from ..models.documents import DocumentDetailResponse


def get_document(document_id: str) -> DocumentDetailResponse:
    """Return a placeholder document payload.

    The persistence layer will later hydrate this object from Postgres. The placeholder
    keeps the API surface usable for front-end development.
    """

    return DocumentDetailResponse(document_id=UUID(document_id), source_type="unknown", passages=[])
