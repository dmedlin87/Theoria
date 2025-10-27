from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from theo.infrastructure.api.app.ingest import parsers  # noqa: E402


@pytest.fixture
def disable_unstructured(monkeypatch):
    """Ensure HTML parsing uses the lightweight fallback extractor."""

    monkeypatch.setattr(parsers, "_parse_html_with_unstructured", lambda path: None)


def test_repro_html_unstructured_signature(tmp_path, monkeypatch):
    """``parse_html_document`` should tolerate legacy helper signatures."""

    monkeypatch.setattr(parsers, "_parse_html_with_unstructured", lambda path: None)

    html = """
    <html>
      <head><title>Sample</title></head>
      <body><p>Hello!</p></body>
    </html>
    """

    path = tmp_path / "sample.html"
    path.write_text(html, encoding="utf-8")

    result = parsers.parse_html_document(path, max_tokens=1000)

    assert result.parser == "html_fallback"
    assert "Hello!" in result.text


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


def _write_malicious_docx(path: Path, *, core_xml: str | None = None, document_xml: str | None = None) -> Path:
    docx_path = path / "malicious.docx"
    with zipfile.ZipFile(docx_path, "w") as handle:
        if core_xml is not None:
            handle.writestr("docProps/core.xml", core_xml)
        if document_xml is not None:
            handle.writestr("word/document.xml", document_xml)
    return docx_path


def test_extract_docx_metadata_rejects_external_entities(tmp_path):
    malicious_core = """<?xml version='1.0' encoding='UTF-8'?>
    <!DOCTYPE foo [<!ELEMENT foo ANY ><!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>
    <cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
                      xmlns:dc='http://purl.org/dc/elements/1.1/'>
      <dc:title>&xxe;</dc:title>
    </cp:coreProperties>
    """
    docx_path = _write_malicious_docx(tmp_path, core_xml=malicious_core)

    with zipfile.ZipFile(docx_path) as handle:
        metadata = parsers._extract_docx_metadata(handle)

    assert metadata == {}


def test_fallback_docx_text_rejects_external_entities(tmp_path):
    malicious_document = """<?xml version='1.0' encoding='UTF-8'?>
    <!DOCTYPE foo [<!ELEMENT foo ANY ><!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
      <w:body>
        <w:p><w:r><w:t>&xxe;</w:t></w:r></w:p>
      </w:body>
    </w:document>
    """
    docx_path = _write_malicious_docx(tmp_path, document_xml=malicious_document)

    text, metadata = parsers._fallback_docx_text(docx_path)

    assert metadata == {}
    assert isinstance(text, str)
