from __future__ import annotations

from typing import Any

from theo.infrastructure.api.app.workers import tasks


class _Recorder:
    def __init__(self) -> None:
        self.called = False
        self.url: str | None = None
        self.json: dict[str, Any] | None = None
        self.headers: dict[str, str] | None = None
        self.timeout: float | None = None

    def __call__(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> "_StubResponse":
        self.called = True
        self.url = url
        self.json = json or {}
        self.headers = headers
        if timeout is not None:
            self.timeout = float(timeout)
        return _StubResponse()


class _StubResponse:
    def raise_for_status(self) -> None:
        return None


def test_send_topic_digest_notification_posts_payload(monkeypatch) -> None:
    recorder = _Recorder()

    monkeypatch.setattr(
        tasks.settings,
        "notification_webhook_url",
        "https://example.invalid/webhook",
        raising=False,
    )
    monkeypatch.setattr(
        tasks.settings,
        "notification_webhook_headers",
        {"Authorization": "Bearer secret"},
        raising=False,
    )
    monkeypatch.setattr(
        tasks.settings,
        "notification_timeout_seconds",
        3.5,
        raising=False,
    )
    monkeypatch.setattr(tasks.httpx, "post", recorder)

    context = {"digest_title": "Weekly summary"}
    recipients = ["alice@example.com", "bob@example.com"]

    tasks.send_topic_digest_notification(
        "digest-doc-123",
        recipients,
        context=context,
    )

    assert recorder.called is True
    assert recorder.url == "https://example.invalid/webhook"
    assert recorder.json == {
        "type": "topic_digest.ready",
        "document_id": "digest-doc-123",
        "recipients": recipients,
        "context": context,
    }
    assert recorder.headers == {"Authorization": "Bearer secret"}
    assert recorder.timeout == 3.5
