from dataclasses import FrozenInstanceError

import pytest

from theo.application.graph import GraphDocumentProjection, GraphProjector, NullGraphProjector


def test_graph_document_projection_defaults_and_immutability() -> None:
    projection = GraphDocumentProjection(document_id="doc-123")

    assert projection.title is None
    assert projection.verses == ()
    assert projection.concepts == ()

    with pytest.raises(FrozenInstanceError):
        projection.title = "New Title"  # type: ignore[misc]


class _ProjectorImpl:
    def __init__(self) -> None:
        self.projected: list[GraphDocumentProjection] = []
        self.removed: list[str] = []

    def project_document(self, projection: GraphDocumentProjection) -> None:
        self.projected.append(projection)

    def remove_document(self, document_id: str) -> None:
        self.removed.append(document_id)


def test_graph_projector_protocol_runtime_check() -> None:
    projector = _ProjectorImpl()

    assert isinstance(projector, GraphProjector)

    payload = GraphDocumentProjection(document_id="doc-1", verses=("John.1.1",))
    projector.project_document(payload)
    projector.remove_document("doc-1")

    assert projector.projected == [payload]
    assert projector.removed == ["doc-1"]


def test_null_projector_is_noop() -> None:
    projector = NullGraphProjector()

    assert projector.project_document(GraphDocumentProjection(document_id="doc")) is None
    assert projector.remove_document("doc") is None
