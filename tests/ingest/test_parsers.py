from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ingest import parsers  # noqa: E402


@pytest.fixture
def disable_unstructured(monkeypatch):
    """Ensure HTML parsing uses the lightweight fallback extractor."""

    monkeypatch.setattr(parsers, "_parse_html_with_unstructured", lambda path: None)


def test_parse_html_document_ignores_script_content(tmp_path, disable_unstructured):
    html = """
    <html>
      <head>
        <title>Inline JS Test</title>
        <script type="text/javascript">
          const secret = "should never surface";
        </script>
      </head>
      <body>
        <h1>Welcome</h1>
        <p>This is <strong>content</strong> for testing.</p>
        <script>
          console.log('still hidden');
        </script>
      </body>
    </html>
    """

    path = tmp_path / "inline-script.html"
    path.write_text(html, encoding="utf-8")

    result = parsers.parse_html_document(path, max_tokens=2000)

    assert result.parser == "html_fallback"
    assert result.metadata.get("title") == "Inline JS Test"
    assert "should never surface" not in result.text
    assert "still hidden" not in result.text
    assert "Welcome" in result.text

    combined_chunks = " \n".join(chunk.text for chunk in result.chunks)
    assert "should never surface" not in combined_chunks
    assert "still hidden" not in combined_chunks
