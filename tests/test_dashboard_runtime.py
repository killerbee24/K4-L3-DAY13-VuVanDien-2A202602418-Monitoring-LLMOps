from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.dashboard import build_dashboard_snapshot, render_dashboard


def _write_logs(path: Path) -> None:
    records = [
        {"ts": "2026-09-30T03:30:00Z", "event": "request_received"},
        {"ts": "2026-09-30T03:30:01Z", "event": "request_received"},
        {"ts": "2026-09-30T03:30:02Z", "event": "request_received"},
        {
            "ts": "2026-09-30T03:30:03Z",
            "event": "response_sent",
            "latency_ms": 100,
            "ttft_ms": 20,
            "cost_usd": 0.1,
            "tokens_in": 20,
            "tokens_out": 80,
            "quality_score": 0.8,
            "tool_name": "retrieval",
            "tool_success": True,
        },
        {
            "ts": "2026-09-30T03:30:04Z",
            "event": "response_sent",
            "latency_ms": 300,
            "ttft_ms": 40,
            "cost_usd": 0.2,
            "tokens_in": 30,
            "tokens_out": 120,
            "quality_score": 0.9,
            "tool_name": "retrieval",
            "tool_success": True,
        },
        {
            "ts": "2026-09-30T03:30:05Z",
            "event": "request_failed",
            "error_type": "RuntimeError",
            "tool_name": "retrieval",
            "tool_success": False,
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_dashboard_snapshot_aggregates_all_six_panels(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    _write_logs(log_path)

    snapshot = build_dashboard_snapshot(
        log_path=log_path,
        now=datetime(2026, 9, 30, 3, 31, tzinfo=timezone.utc),
    )

    panels = {panel["id"]: panel for panel in snapshot["panels"]}
    assert set(panels) == {"latency", "traffic", "errors", "cost", "tokens", "quality"}
    assert panels["latency"]["values"] == {
        "p50": 100.0,
        "p95": 300.0,
        "p99": 300.0,
        "ttft_p95": 40.0,
    }
    assert panels["traffic"]["values"]["count"] == 3
    assert panels["errors"]["values"]["error_rate_pct"] == 33.33
    assert panels["errors"]["values"]["tool_success_rate_pct"] == 66.67
    assert panels["cost"]["values"]["total"] == 0.3
    assert panels["tokens"]["values"]["tokens_in"] == 50
    assert panels["tokens"]["values"]["tokens_out"] == 200
    assert panels["quality"]["values"]["mean"] == 0.85


def test_rendered_dashboard_has_six_named_panels_and_runtime_context(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "logs.jsonl"
    _write_logs(log_path)
    snapshot = build_dashboard_snapshot(
        log_path=log_path,
        now=datetime(2026, 9, 30, 3, 31, tzinfo=timezone.utc),
    )

    html = render_dashboard(snapshot)

    assert html.count('data-panel-id="') == 6
    assert "Latency percentiles and TTFT" in html
    assert "Error rate and retrieval success" in html
    assert "Time range: last 60 minutes" in html
    assert "Refresh: 30 seconds" in html
    assert "Threshold/SLO" in html
