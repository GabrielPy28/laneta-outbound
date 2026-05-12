from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import Settings
from app.services import postmaster_domain_status as m


def test_domain_status_uses_worst_day_in_window(monkeypatch) -> None:
    """El score debe reflejar picos en días anteriores, no solo el último día."""

    def fake_list_traffic_stats(_settings: Settings, *, domain: str, page_size: int = 10):
        return [
            {
                "date": {"year": 2026, "month": 5, "day": 9},
                "domainReputation": "HIGH",
                "spamRate": 0.001,
                "userReportedSpamRatio": None,
                "dkimSuccessRate": 0.99,
                "spfSuccessRate": 0.99,
                "dmarcSuccessRate": 0.99,
                "inboundEncryptionRatio": 0.99,
                "deliveryErrorRate": 0.0,
            },
            {
                "date": {"year": 2026, "month": 5, "day": 8},
                "domainReputation": "HIGH",
                "spamRate": 0.05,
                "userReportedSpamRatio": None,
                "dkimSuccessRate": 0.85,
                "spfSuccessRate": 0.99,
                "dmarcSuccessRate": 0.99,
                "inboundEncryptionRatio": 0.99,
                "deliveryErrorRate": 0.0,
            },
        ]

    monkeypatch.setattr(m, "list_traffic_stats", fake_list_traffic_stats)
    settings = MagicMock(spec=Settings)
    settings.domains_registry_file = "/nonexistent/postmaster_domains_registry.json"

    report = m.get_domain_status_report(settings, domain="example.com")

    assert report.evaluated_date == "2026-05-09"
    assert report.key_metrics.get("score_uses_worst_in_window") is True
    assert report.key_metrics["spam_rate"] == 0.05
    assert report.key_metrics["dkim_success_rate"] == 0.85
    dates = [row["date"] for row in report.key_metrics["daily_history"]]
    assert "2026-05-09" in dates and "2026-05-08" in dates
    assert report.score < 80
