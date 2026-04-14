"""
AlertReader ir vertimų žodyno testai.
"""
import json
import os
import tempfile

import pytest

from app.services.alert_reader import AlertReader, _translate, _TRANSLATIONS


class TestTranslations:
    def test_all_known_types_have_title(self):
        for alert_type in _TRANSLATIONS:
            title, explanation, recommendation = _translate(alert_type)
            assert title
            assert explanation
            assert recommendation

    def test_unknown_type_returns_default(self):
        title, explanation, recommendation = _translate("niekada_neegzistavo")
        assert title
        assert recommendation

    def test_ssh_bruteforce_translation(self):
        title, _, _ = _translate("ssh_bruteforce")
        assert "SSH" in title

    def test_all_six_types_covered(self):
        expected = {
            "ssh_bruteforce", "invalid_user_scan", "firewall_spike",
            "log_volume_spike", "high_error_rate", "ml_anomaly",
        }
        assert expected == set(_TRANSLATIONS.keys())


class TestAlertReader:
    def test_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANOMALY_DB_PATH", str(tmp_path / "missing.json"))
        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()
        assert reader.read_all() == []

    def test_reads_alerts_newest_first(self, tmp_path, monkeypatch):
        path = tmp_path / "anomaly_history.json"
        alerts = [
            {"timestamp": "2024-01-01T00:00:00", "severity": "low",
             "detection_method": "rule", "alert_type": "ssh_bruteforce",
             "description": "", "source_ip": "1.2.3.4", "source_host": "", "details": {}},
            {"timestamp": "2024-01-02T00:00:00", "severity": "high",
             "detection_method": "rule", "alert_type": "firewall_spike",
             "description": "", "source_ip": "", "source_host": "", "details": {}},
        ]
        path.write_text(json.dumps(alerts), encoding="utf-8")
        monkeypatch.setenv("ANOMALY_DB_PATH", str(path))

        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()
        result = reader.read_all()

        assert len(result) == 2
        # Naujesnis pirmas
        assert result[0].timestamp == "2024-01-02T00:00:00"
        assert result[1].timestamp == "2024-01-01T00:00:00"

    def test_alert_item_has_translation_fields(self, tmp_path, monkeypatch):
        path = tmp_path / "anomaly_history.json"
        path.write_text(json.dumps([{
            "timestamp": "2024-01-01T10:00:00", "severity": "medium",
            "detection_method": "statistical", "alert_type": "high_error_rate",
            "description": "", "source_ip": "", "source_host": "", "details": {},
        }]), encoding="utf-8")
        monkeypatch.setenv("ANOMALY_DB_PATH", str(path))

        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()
        items = reader.read_all()

        assert len(items) == 1
        item = items[0]
        assert item.title
        assert item.explanation
        assert item.recommendation
        assert "Rekomenduojama" in item.recommendation

    def test_read_recent_limits(self, tmp_path, monkeypatch):
        path = tmp_path / "anomaly_history.json"
        alerts = [
            {"timestamp": f"2024-01-{i:02d}T00:00:00", "severity": "low",
             "detection_method": "rule", "alert_type": "ssh_bruteforce",
             "description": "", "source_ip": "", "source_host": "", "details": {}}
            for i in range(1, 11)
        ]
        path.write_text(json.dumps(alerts), encoding="utf-8")
        monkeypatch.setenv("ANOMALY_DB_PATH", str(path))

        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()

        assert len(reader.read_recent(limit=3)) == 3
        assert len(reader.read_recent(limit=100)) == 10

    def test_pagination(self, tmp_path, monkeypatch):
        path = tmp_path / "anomaly_history.json"
        alerts = [
            {"timestamp": f"2024-01-{i:02d}T00:00:00", "severity": "low",
             "detection_method": "rule", "alert_type": "firewall_spike",
             "description": "", "source_ip": "", "source_host": "", "details": {}}
            for i in range(1, 16)  # 15 alertų
        ]
        path.write_text(json.dumps(alerts), encoding="utf-8")
        monkeypatch.setenv("ANOMALY_DB_PATH", str(path))

        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()

        page1, total = reader.read_page(page=1, size=10)
        assert total == 15
        assert len(page1) == 10

        page2, _ = reader.read_page(page=2, size=10)
        assert len(page2) == 5

    def test_handles_corrupt_json(self, tmp_path, monkeypatch):
        path = tmp_path / "anomaly_history.json"
        path.write_text("{ not valid json [[[", encoding="utf-8")
        monkeypatch.setenv("ANOMALY_DB_PATH", str(path))

        import importlib
        import app.services.alert_reader as mod
        importlib.reload(mod)
        reader = mod.AlertReader()
        assert reader.read_all() == []
