from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_slo_has_explicit_error_budget_calculation() -> None:
    slo = yaml.safe_load(
        (REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8")
    )
    primary = slo["primary_slo"]

    assert primary["target_percent"] == 99.5
    assert primary["error_budget_percent"] == 0.5
    assert primary["error_budget"]["allowed_bad_events_per_10000_requests"] == 50
    assert "3000" in primary["sli"]["good_event"]


def test_three_alerts_are_symptom_based_and_actionable() -> None:
    payload = yaml.safe_load(
        (REPO_ROOT / "config" / "alert_rules.yaml").read_text(encoding="utf-8")
    )
    alerts = payload["alerts"]

    assert len(alerts) == 3
    assert {alert["name"] for alert in alerts} == {
        "HighLatencyP95",
        "HighRequestErrorRate",
        "LowRetrievalSuccess",
    }
    for alert in alerts:
        assert alert["type"] == "symptom-based"
        assert alert["severity"] in {"warning", "critical"}
        assert alert["duration"].endswith("m")
        assert alert["channel"] == "slack"
        assert alert["slack_channel"] == "#k4-l3b-alerts"
        assert alert["owner"] == "student-2A202602418"
        assert alert["runbook"].startswith("docs/alerts.md#alert-")
        assert "TODO" not in str(alert)
