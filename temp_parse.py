from textwrap import dedent
from types import SimpleNamespace
from theo.services.api.app.ingest.osis import parse_osis_document
from theo.services.api.app.ingest.stages.parsers import OsisCommentaryParser
from theo.application.facades.settings import get_settings

payload = dedent("""
<osis>
  <osisText osisIDWork="Commentary.Work">
    <div type="commentary">
      <verse osisID="John.1.1">In the beginning was the Word.
        <note type="commentary" osisRef="John.1.1">Initial insight.</note>
      </verse>
      <verse osisID="John.1.2 John.1.3">He was with God in the beginning.
        <note type="commentary" osisRef="John.1.2 John.1.3">
          Shared reflection.
        </note>
      </verse>
    </div>
  </osisText>
</osis>
""")

doc = parse_osis_document(payload)
parser = OsisCommentaryParser()
context = SimpleNamespace(
    settings=get_settings(),
    instrumentation=SimpleNamespace(set=lambda *args, **kwargs: None),
)
state = {"osis_document": doc, "frontmatter": {"tags": ["alpha"]}}
result = parser.parse(context=context, state=state)
print(result["commentary_entries"])
