import httpx
import pytest

from theo.services.api.app.analytics.openalex import OpenAlexClient


@pytest.mark.parametrize(
    ("input_doi", "expected_url"),
    [
        (
            "https://doi.org/10.1234/example",
            "https://api.openalex.org/works/https://doi.org/10.1234/example?select=concepts",
        ),
        (
            "10.1234/example",
            "https://api.openalex.org/works/https://doi.org/10.1234/example?select=concepts",
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
        if request.url.path.startswith("/works/https://doi.org/"):
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


def test_fetch_authorships_retries_after_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, json={}, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "authorships": [
                    {"author": {"display_name": "First Author"}},
                ]
            },
        )

    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "theo.services.api.app.analytics.openalex.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    authorships = openalex.fetch_authorships("W123")

    assert authorships == [{"author": {"display_name": "First Author"}}]
    assert sleep_calls  # ensure rate-limit pause executed


def test_fetch_citations_collects_paginated_results() -> None:
    cursor_requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/works/W123":
            return httpx.Response(
                200,
                json={"referenced_works": ["W10", "W20"]},
            )

        if request.url.path == "/works/W123/cited-by":
            cursor = request.url.params.get("cursor")
            cursor_requests.append(cursor)
            if cursor == "*":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "https://openalex.org/W900",
                                "display_name": "First Citation",
                                "doi": "10.1/example",
                                "authorships": [
                                    {"author": {"display_name": "Author One"}},
                                    {"author": {"display_name": "Author Two"}},
                                ],
                            },
                        ],
                        "meta": {"next_cursor": "abc"},
                    },
                )
            if cursor == "abc":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "https://openalex.org/W901",
                                "display_name": "Second Citation",
                                "publication_year": 2024,
                            }
                        ],
                        "meta": {},
                    },
                )
        pytest.fail(f"Unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    citations = openalex.fetch_citations("W123")

    assert citations["referenced"] == ["W10", "W20"]
    assert citations["cited_by"] == [
        {
            "id": "https://openalex.org/W900",
            "display_name": "First Citation",
            "doi": "10.1/example",
            "authors": ["Author One", "Author Two"],
        },
        {
            "id": "https://openalex.org/W901",
            "display_name": "Second Citation",
            "publication_year": 2024,
        },
    ]
    assert cursor_requests == ["*", "abc"]


def test_fetch_work_metadata_prefers_openalex_identifier() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/works/W999":
            return httpx.Response(200, json={"id": "https://openalex.org/W999"})
        pytest.fail(f"Unexpected request path: {request.url.path}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    openalex = OpenAlexClient(client)

    work = openalex.fetch_work_metadata(openalex_id="W999", doi="10.1/example")

    assert requested_paths == ["/works/W999"]
    assert work == {"id": "https://openalex.org/W999"}
