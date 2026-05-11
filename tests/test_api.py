"""Integration tests for FastAPI endpoints — TDD RED gate.

InfluxDB is mocked at the query_api level; no real server required.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import main
from main import app
from fastapi.testclient import TestClient

http = TestClient(app)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class _Rec:
    """Minimal stand-in for an InfluxDB FluxRecord."""

    def __init__(self, arm_id, sensor, value, fault_mode="normal",
                 z_score=0.0, is_anomaly=0, ts=None):
        self._time = ts or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.values = {
            "arm_id": arm_id,
            "sensor": sensor,
            "value": value,
            "fault_mode": fault_mode,
            "z_score": z_score,
            "is_anomaly": is_anomaly,
        }

    def get_time(self):
        return self._time


class _Table:
    def __init__(self, records):
        self.records = records


def _tables(*records):
    return [_Table(list(records))]


@pytest.fixture(autouse=True)
def mock_query(monkeypatch):
    """Replace query_api with a MagicMock before every test."""
    mq = MagicMock()
    monkeypatch.setattr(main, "query_api", mq)
    return mq


# ---------------------------------------------------------------------------
# GET /api/sensors/latest
# ---------------------------------------------------------------------------

class TestGetLatest:
    def test_returns_200(self, mock_query):
        mock_query.query.return_value = []
        r = http.get("/api/sensors/latest")
        assert r.status_code == 200

    def test_all_arms_present_even_when_empty(self, mock_query):
        mock_query.query.return_value = []
        data = http.get("/api/sensors/latest").json()
        assert set(data.keys()) == {"arm_01", "arm_02", "arm_03"}

    def test_default_fault_mode_is_normal(self, mock_query):
        mock_query.query.return_value = []
        data = http.get("/api/sensors/latest").json()
        for arm in data.values():
            assert arm["fault_mode"] == "NORMAL"

    def test_sensor_value_returned(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 72.5, fault_mode="thermal_drift"),
        )
        data = http.get("/api/sensors/latest").json()
        assert data["arm_01"]["temperature"] == 72.5

    def test_fault_mode_uppercased(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 72.5, fault_mode="thermal_drift"),
        )
        data = http.get("/api/sensors/latest").json()
        assert data["arm_01"]["fault_mode"] == "THERMAL_DRIFT"

    def test_unknown_arm_ignored(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_99", "temperature", 50.0),
        )
        data = http.get("/api/sensors/latest").json()
        assert "arm_99" not in data

    def test_unknown_sensor_ignored(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "pressure", 100.0),
        )
        data = http.get("/api/sensors/latest").json()
        assert "pressure" not in data["arm_01"]

    def test_most_recent_record_wins(self, mock_query):
        t_old = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 60.0, ts=t_old),
            _Rec("arm_01", "temperature", 80.0, ts=t_new),
        )
        data = http.get("/api/sensors/latest").json()
        assert data["arm_01"]["temperature"] == 80.0


# ---------------------------------------------------------------------------
# GET /api/sensors/history
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_returns_200(self, mock_query):
        mock_query.query.return_value = []
        r = http.get("/api/sensors/history")
        assert r.status_code == 200

    def test_structure_contains_all_arms_and_sensors(self, mock_query):
        mock_query.query.return_value = []
        data = http.get("/api/sensors/history").json()
        assert set(data.keys()) == {"arm_01", "arm_02", "arm_03"}
        for arm in data.values():
            assert set(arm.keys()) == {"temperature", "vibration", "current"}

    def test_records_contain_t_v_z_keys(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 70.0, z_score=1.2),
        )
        data = http.get("/api/sensors/history").json()
        record = data["arm_01"]["temperature"][0]
        assert "t" in record and "v" in record and "z" in record

    def test_history_sorted_ascending_by_time(self, mock_query):
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 80.0, ts=t1),
            _Rec("arm_01", "temperature", 70.0, ts=t2),
        )
        data = http.get("/api/sensors/history").json()
        times = [r["t"] for r in data["arm_01"]["temperature"]]
        assert times == sorted(times)

    def test_minutes_param_out_of_range_low(self, mock_query):
        mock_query.query.return_value = []
        r = http.get("/api/sensors/history?minutes=0")
        assert r.status_code == 422

    def test_minutes_param_out_of_range_high(self, mock_query):
        mock_query.query.return_value = []
        r = http.get("/api/sensors/history?minutes=61")
        assert r.status_code == 422

    def test_minutes_param_accepted_at_bounds(self, mock_query):
        mock_query.query.return_value = []
        assert http.get("/api/sensors/history?minutes=1").status_code == 200
        assert http.get("/api/sensors/history?minutes=60").status_code == 200


# ---------------------------------------------------------------------------
# GET /api/anomalies
# ---------------------------------------------------------------------------

class TestGetAnomalies:
    def test_returns_200(self, mock_query):
        mock_query.query.return_value = []
        r = http.get("/api/anomalies")
        assert r.status_code == 200

    def test_returns_empty_list_when_no_anomalies(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 60.0, is_anomaly=0),
        )
        data = http.get("/api/anomalies").json()
        assert data == []

    def test_only_anomaly_records_returned(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 60.0, is_anomaly=0),
            _Rec("arm_02", "vibration", 9.5, is_anomaly=1, z_score=4.2),
        )
        data = http.get("/api/anomalies").json()
        assert len(data) == 1
        assert data[0]["arm"] == "arm_02"

    def test_anomaly_record_has_required_fields(self, mock_query):
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "current", 15.0, is_anomaly=1, z_score=5.1,
                 fault_mode="overcurrent"),
        )
        data = http.get("/api/anomalies").json()
        rec = data[0]
        assert {"ts", "arm", "sensor", "value", "z", "fault_mode"} <= set(rec.keys())

    def test_anomalies_sorted_newest_first(self, mock_query):
        t1 = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_query.query.return_value = _tables(
            _Rec("arm_01", "temperature", 80.0, is_anomaly=1, ts=t1),
            _Rec("arm_02", "vibration", 9.0, is_anomaly=1, ts=t2),
        )
        data = http.get("/api/anomalies").json()
        assert data[0]["ts"] > data[1]["ts"]

    def test_anomalies_capped_at_200(self, mock_query):
        records = [_Rec("arm_01", "temperature", 99.0, is_anomaly=1) for _ in range(250)]
        mock_query.query.return_value = [_Table(records)]
        data = http.get("/api/anomalies").json()
        assert len(data) == 200
