from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app
from app.pii import hash_user_id


def _post_chat(payload: dict[str, str], request_id: str | None = None) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {"x-request-id": request_id} if request_id else {}
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post("/chat", json=payload, headers=headers)

    return asyncio.run(send_request())


def _read_events(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_generated_correlation_id_is_propagated_and_logs_are_enriched(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setenv("APP_ENV", "test")
    payload = {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "Explain observability",
    }

    response = _post_chat(payload)

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert float(response.headers["x-response-time-ms"]) >= 0

    api_events = [event for event in _read_events(log_path) if event["service"] == "api"]
    assert {event["correlation_id"] for event in api_events} == {correlation_id}
    for event in api_events:
        assert event["user_id_hash"] == hash_user_id(payload["user_id"])
        assert event["session_id"] == payload["session_id"]
        assert event["feature"] == payload["feature"]
        assert event["model"] == "claude-sonnet-4-5"
        assert event["env"] == "test"


def test_incoming_request_id_is_reused_and_pii_is_redacted(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    pii_samples = (
        ("Email student@vinuni.edu.vn", "student@vinuni.edu.vn", "EMAIL"),
        ("Phone 090 123 4567", "090 123 4567", "PHONE_VN"),
        ("CCCD 079203001234", "079203001234", "CCCD"),
        ("Card 4111 1111 1111 1111", "4111 1111 1111 1111", "CREDIT_CARD"),
    )

    for index, (message, _, _) in enumerate(pii_samples, start=1):
        request_id = f"req-client{index:02d}"
        response = _post_chat(
            {
                "user_id": "student-02",
                "session_id": "session-02",
                "feature": "qa",
                "message": message,
            },
            request_id=request_id,
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == request_id
        assert response.json()["correlation_id"] == request_id

    raw_log = log_path.read_text(encoding="utf-8")
    for _, raw_pii, marker in pii_samples:
        assert raw_pii not in raw_log
        assert f"[REDACTED_{marker}]" in raw_log
