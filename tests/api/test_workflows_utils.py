from theo.services.api.app.models.search import HybridSearchFilters
from theo.services.api.app.routes.ai.workflows.utils import has_filters


def test_has_filters_returns_false_for_empty_filters() -> None:
    assert has_filters(None) is False
    assert has_filters(HybridSearchFilters()) is False


def test_has_filters_returns_true_when_field_present() -> None:
    filters = HybridSearchFilters(collection="Sermons")
    assert has_filters(filters) is True
