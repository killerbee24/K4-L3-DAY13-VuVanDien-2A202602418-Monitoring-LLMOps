from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
DEFAULT_LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return float(ordered[index])


def _load_config(config_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dashboard = payload.get("dashboard") if isinstance(payload, dict) else None
    if not isinstance(dashboard, dict):
        raise ValueError("Invalid dashboard config: missing dashboard object")
    return dashboard


def _load_recent_records(
    log_path: Path,
    *,
    window_minutes: int,
    now: datetime,
) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []

    cutoff = now - timedelta(minutes=window_minutes)
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is not None and cutoff <= timestamp <= now:
            records.append(record)
    return records


def _number(record: dict[str, Any], field: str) -> float | None:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _meets_threshold(value: float, threshold: dict[str, Any]) -> bool:
    target = float(threshold["value"])
    if threshold["operator"] == "lte":
        return value <= target
    return value >= target


def build_dashboard_snapshot(
    *,
    log_path: Path = DEFAULT_LOG_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    dashboard = _load_config(config_path)
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_minutes = int(dashboard["time_range_minutes"])
    records = _load_recent_records(
        log_path,
        window_minutes=window_minutes,
        now=current_time,
    )

    request_events = [record for record in records if record.get("event") == "request_received"]
    response_events = [record for record in records if record.get("event") == "response_sent"]
    failed_events = [record for record in records if record.get("event") == "request_failed"]

    latencies = [
        value
        for record in response_events
        if (value := _number(record, "latency_ms")) is not None
    ]
    ttfts = [
        value
        for record in response_events
        if (value := _number(record, "ttft_ms")) is not None
    ]
    costs = [
        value
        for record in response_events
        if (value := _number(record, "cost_usd")) is not None
    ]
    quality_scores = [
        value
        for record in response_events
        if (value := _number(record, "quality_score")) is not None
    ]

    minute_counts = Counter()
    for record in request_events:
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is not None:
            minute_counts[timestamp.strftime("%Y-%m-%dT%H:%M")] += 1
    latest_rate = float(minute_counts[max(minute_counts)]) if minute_counts else 0.0

    tool_events = [
        record
        for record in records
        if record.get("tool_name") == "retrieval"
        and isinstance(record.get("tool_success"), bool)
    ]
    retrieval_success = (
        100.0
        * sum(record["tool_success"] is True for record in tool_events)
        / len(tool_events)
        if tool_events
        else 0.0
    )
    error_rate = (
        100.0 * len(failed_events) / len(request_events) if request_events else 0.0
    )
    error_breakdown = Counter(
        str(record.get("error_type") or "unknown") for record in failed_events
    )

    tokens_in = int(
        sum(_number(record, "tokens_in") or 0 for record in response_events)
    )
    tokens_out = int(
        sum(_number(record, "tokens_out") or 0 for record in response_events)
    )

    panel_values: dict[str, dict[str, float | int]] = {
        "latency": {
            "p50": round(_percentile(latencies, 50), 2),
            "p95": round(_percentile(latencies, 95), 2),
            "p99": round(_percentile(latencies, 99), 2),
            "ttft_p95": round(_percentile(ttfts, 95), 2),
        },
        "traffic": {
            "count": len(request_events),
            "rate_per_minute": round(latest_rate, 2),
        },
        "errors": {
            "error_rate_pct": round(error_rate, 2),
            "tool_success_rate_pct": round(retrieval_success, 2),
        },
        "cost": {
            "total": round(sum(costs), 6),
            "sum_by_minute": round(sum(costs), 6),
        },
        "tokens": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "sum_by_field": tokens_in + tokens_out,
        },
        "quality": {
            "mean": round(mean(quality_scores), 4) if quality_scores else 0.0,
        },
    }

    panels: list[dict[str, Any]] = []
    for panel in dashboard["panels"]:
        panel_id = panel["id"]
        values = panel_values[panel_id]
        threshold = panel["threshold"]
        threshold_value = float(values[threshold["aggregation"]])
        panels.append(
            {
                "id": panel_id,
                "title": panel["title"],
                "unit": panel["unit"],
                "values": values,
                "threshold": threshold,
                "healthy": _meets_threshold(threshold_value, threshold),
                "error_breakdown": dict(error_breakdown) if panel_id == "errors" else {},
            }
        )

    return {
        "title": dashboard["title"],
        "generated_at": current_time.isoformat(),
        "window_start": (current_time - timedelta(minutes=window_minutes)).isoformat(),
        "time_range_minutes": window_minutes,
        "refresh_seconds": int(dashboard["refresh_seconds"]),
        "source": str(log_path).replace("\\", "/"),
        "records_analyzed": len(records),
        "panels": panels,
    }


def _format_value(value: float | int, unit: str) -> str:
    if unit == "usd":
        return "$" + f"{float(value):.6f}"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.2f}"


def render_dashboard(snapshot: dict[str, Any]) -> str:
    panel_html: list[str] = []
    for panel in snapshot["panels"]:
        metrics = "".join(
            (
                '<div class="metric">'
                f"<span>{escape(name.replace('_', ' ').upper())}</span>"
                f"<strong>{escape(_format_value(value, panel['unit']))}</strong>"
                "</div>"
            )
            for name, value in panel["values"].items()
            if name != "sum_by_field"
        )
        breakdown = ""
        if panel["error_breakdown"]:
            items = ", ".join(
                f"{escape(name)}: {count}"
                for name, count in sorted(panel["error_breakdown"].items())
            )
            breakdown = f'<p class="detail">Error breakdown: {items}</p>'
        threshold = panel["threshold"]
        operator = "≤" if threshold["operator"] == "lte" else "≥"
        state = "healthy" if panel["healthy"] else "breach"
        panel_html.append(
            f'<section class="panel {state}" data-panel-id="{escape(panel["id"])}">'
            f"<header><h2>{escape(panel['title'])}</h2>"
            f'<span class="status">{state.upper()}</span></header>'
            f'<div class="metrics">{metrics}</div>'
            f"{breakdown}"
            '<div class="threshold">'
            f"Threshold/SLO: {escape(threshold['aggregation'])} {operator} "
            f"{escape(str(threshold['value']))} {escape(panel['unit'])}"
            "</div></section>"
        )

    no_data = (
        '<p class="notice">No records found in the selected time range.</p>'
        if snapshot["records_analyzed"] == 0
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{snapshot['refresh_seconds']}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(snapshot['title'])}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; background: #0b1020; color: #eef2ff; }}
    main {{ max-width: 1280px; margin: auto; padding: 28px; }}
    .meta {{ color: #a9b4cc; margin-bottom: 20px; line-height: 1.6; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
    .panel {{ background: #151d32; border: 1px solid #2a3654; border-radius: 14px;
              padding: 18px; min-height: 210px; }}
    .panel.healthy {{ border-top: 4px solid #34d399; }}
    .panel.breach {{ border-top: 4px solid #fb7185; }}
    header {{ display: flex; justify-content: space-between; gap: 12px; }}
    h1 {{ margin-bottom: 8px; }} h2 {{ font-size: 1rem; margin: 0; }}
    .status {{ font-size: .72rem; font-weight: 800; }}
    .healthy .status {{ color: #6ee7b7; }} .breach .status {{ color: #fda4af; }}
    .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
                margin: 20px 0; }}
    .metric {{ background: #0f172a; border-radius: 9px; padding: 12px; }}
    .metric span {{ display: block; color: #94a3b8; font-size: .68rem; }}
    .metric strong {{ display: block; margin-top: 5px; font-size: 1.2rem; }}
    .threshold {{ border-top: 1px solid #2a3654; color: #cbd5e1;
                  font-size: .78rem; padding-top: 12px; }}
    .detail, .notice {{ color: #fbbf24; font-size: .82rem; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(snapshot['title'])}</h1>
    <div class="meta">
      Time range: last {snapshot['time_range_minutes']} minutes ·
      Refresh: {snapshot['refresh_seconds']} seconds ·
      Source: {escape(snapshot['source'])} ·
      Records: {snapshot['records_analyzed']}
    </div>
    {no_data}
    <div class="grid">{''.join(panel_html)}</div>
  </main>
</body>
</html>"""
