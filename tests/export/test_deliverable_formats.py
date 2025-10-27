from __future__ import annotations

import pytest

from theo.infrastructure.api.app.routes import export as export_routes


def test_normalise_formats_translates_aliases() -> None:
    result = export_routes._normalise_formats(["md", "PDF", "markdown"])
    assert result == ["markdown", "pdf"]


def test_normalise_formats_rejects_unknown() -> None:
    with pytest.raises(export_routes.ExportError) as excinfo:
        export_routes._normalise_formats(["html"])
    assert "Unsupported deliverable format" in str(excinfo.value)
