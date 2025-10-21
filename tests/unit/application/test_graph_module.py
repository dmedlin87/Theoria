from dataclasses import FrozenInstanceError

import pytest

from theo.application import graph


def test_graph_document_projection_defaults_and_fields():
    projection = graph.GraphDocumentProjection(
        document_id="doc-1",
        title="Sample Document",
        verses=("John.3.16",),
    )

    assert projection.document_id == "doc-1"
    assert projection.title == "Sample Document"
    # Ensure optional tuple fields default to empty tuples rather than mutable lists.
    assert projection.concepts == ()
    assert projection.topic_domains == ()
    assert projection.theological_tradition is None


def test_graph_document_projection_is_frozen():
    projection = graph.GraphDocumentProjection(document_id="doc-2")

    with pytest.raises(FrozenInstanceError):
        projection.title = "Cannot mutate"  # type: ignore[misc]


def test_null_graph_projector_runtime_check_and_noops():
    projector = graph.NullGraphProjector()
    projection = graph.GraphDocumentProjection(
        document_id="doc-3",
        title="Immutable Doc",
        verses=("Genesis.1.1",),
        concepts=("creation",),
    )

    assert isinstance(projector, graph.GraphProjector)
    assert projector.project_document(projection) is None
    assert projector.remove_document("doc-3") is None
