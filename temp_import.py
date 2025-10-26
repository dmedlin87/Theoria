from pathlib import Path
from sqlalchemy.orm import Session
from tests.ingest.test_osis_import import _write_sample_osis, _prepare_db
from theo.application.facades.database import get_engine, get_settings
from theo.services.api.app.ingest.pipeline import PipelineDependencies, import_osis_commentary

base_dir = Path("temp_test_dir")
base_dir.mkdir(exist_ok=True)
_prepare_db(base_dir)
engine = get_engine()
osis_path = base_dir / "commentary.xml"
_write_sample_osis(osis_path)
settings = get_settings()
deps = PipelineDependencies(settings=settings)
with Session(engine) as session:
    result = import_osis_commentary(
        session,
        osis_path,
        frontmatter={"source": "Test Source", "perspective": "Devotional", "tags": ["alpha", "beta"]},
        dependencies=deps,
    )
    print(result)
