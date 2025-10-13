import httpx
import pytest

from theo.services.api.app.analytics.openalex import OpenAlexClient


@pytest.mark.parametrize(
    ("input_doi", "expected_url"),
    [
        (
            "https://doi.org/10.1234/example",
            "https://api.openalex.org/works/https://doi.org/10.1234/example",
        ),
        (
            "10.1234/example",
            "https://api.openalex.org/works/https://doi.org/10.1234/example",
        ),
    ],
)
def test_fetch_topics_doi_variants(input_doi: str, expected_url: str) -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        payload = {
            "concepts": [
                {"display_name": "Topic A"},
                {"display_name": "Topic B"},
            ]
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    topics = openalex.fetch_topics(doi=input_doi)

    assert topics == ["Topic A", "Topic B"]
    assert requested_urls == [expected_url]


def test_fetch_topics_title_search_with_concepts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("search") == "Example Title"
        assert request.url.params.get("per-page") == "1"
        payload = {
            "results": [
                {
                    "concepts": [
                        {"display_name": "Alpha"},
                        {"display_name": "Beta"},
                    ]
                }
            ]
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    topics = openalex.fetch_topics(title="Example Title")

    assert topics == ["Alpha", "Beta"]


def test_fetch_topics_title_search_without_concepts_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"results": [{"id": "W123"}]}
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    topics = openalex.fetch_topics(title="Missing Concepts")

    assert topics == []


def test_fetch_topics_falls_back_to_title_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "https://doi.org/" in request.url.path:
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)
        payload = {
            "results": [
                {
                    "concepts": [
                        {"display_name": "Fallback"},
                    ]
                }
            ]
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    topics = openalex.fetch_topics(doi="10.9999/failure", title="Fallback Title")

    assert topics == ["Fallback"]


def test_fetch_topics_returns_empty_after_all_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("fail", request=request, response=response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    topics = openalex.fetch_topics(doi="10.9999/failure", title="Fallback Title")

    assert topics == []


def test_parse_topics_dedupes_and_ignores_malformed_entries() -> None:
    openalex = OpenAlexClient(httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    payload = {
        "concepts": [
            {"display_name": "Alpha"},
            {"display_name": "Alpha"},  # duplicate
            {"display_name": "Beta"},
            {"display_name": None},
            "not-a-mapping",
            {"no_display_name": "ignored"},
            {"display_name": "Gamma"},
        ]
    }

    topics = openalex._parse_topics(payload)

    assert topics == ["Alpha", "Beta", "Gamma"]
