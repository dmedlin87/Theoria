from pathlib import Path
from types import SimpleNamespace
from theo.services.api.app.ingest.stages.fetchers import OsisSourceFetcher
from theo.services.api.app.ingest.stages.parsers import OsisCommentaryParser
from theo.application.facades.settings import get_settings

tmp_path = Path("temp_commentary.xml")
tmp_path.write_text("""
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
""", encoding="utf-8")

fetcher = OsisSourceFetcher(path=tmp_path, frontmatter={"source": "Test", "perspective": "Devotional", "tags": ["alpha", "beta"]})
settings = get_settings()
context = SimpleNamespace(settings=settings, instrumentation=SimpleNamespace(set=lambda *args, **kwargs: None))
state: dict = {}
state = fetcher.fetch(context=context, state=state)
parser = OsisCommentaryParser()
result = parser.parse(context=context, state=state)
print(result["commentary_entries"])
