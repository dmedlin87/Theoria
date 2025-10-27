from theo.infrastructure.api.app.enrich.metadata import _extract_doi_from_url


def test_repro_uppercase_doi_url() -> None:
    url = "HTTPS://DOI.ORG/10.1234/ABC.DEF"
    assert _extract_doi_from_url(url) == "10.1234/ABC.DEF"
