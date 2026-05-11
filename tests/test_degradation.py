"""Unit tests for DegradationEngine — TDD RED gate."""
import math
import random
from unittest.mock import patch

import pytest

from degradation import DegradationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_at_fault(arm_id="arm_01", mode="thermal_drift", step=50, fault_at=0, duration=100):
    """Return an engine already in a given fault mode at a specific progress."""
    e = DegradationEngine(arm_id)
    e.mode = mode
    e._fault_at = fault_at
    e._fault_duration = duration
    e.step = step
    return e


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_starts_normal(self):
        e = DegradationEngine("arm_01")
        assert e.mode == "normal"

    def test_step_zero(self):
        e = DegradationEngine("arm_01")
        assert e.step == 0

    def test_arm_id_stored(self):
        e = DegradationEngine("arm_99")
        assert e.arm_id == "arm_99"

    def test_fault_scheduled_in_valid_range(self):
        e = DegradationEngine("arm_01")
        # _fault_at is step(0) + randint(60,180)
        assert 60 <= e._fault_at <= 180

    def test_fault_duration_in_valid_range(self):
        e = DegradationEngine("arm_01")
        assert 20 <= e._fault_duration <= 60


# ---------------------------------------------------------------------------
# Normal mode — apply() is a pass-through
# ---------------------------------------------------------------------------

class TestNormalApply:
    @pytest.mark.parametrize("sensor,value", [
        ("temperature", 60.0),
        ("vibration", 1.5),
        ("current", 5.0),
    ])
    def test_normal_returns_base(self, sensor, value):
        e = DegradationEngine("arm_01")
        assert e.mode == "normal"
        assert e.apply(sensor, value) == value


# ---------------------------------------------------------------------------
# tick()
# ---------------------------------------------------------------------------

class TestTick:
    def test_increments_step(self):
        e = DegradationEngine("arm_01")
        e.tick()
        assert e.step == 1
        e.tick()
        assert e.step == 2

    def test_stays_normal_before_fault_at(self):
        e = DegradationEngine("arm_01")
        e._fault_at = 5
        e._fault_duration = 30
        for _ in range(4):  # step reaches 4 — fault_at is 5
            e.tick()
        assert e.mode == "normal"

    def test_transitions_to_fault_at_fault_at(self):
        e = DegradationEngine("arm_01")
        e._fault_at = 5
        e._fault_duration = 30
        for _ in range(4):
            e.tick()
        with patch.object(random, "choice", return_value="thermal_drift"):
            e.tick()  # step = 5 → fault_active
        assert e.mode == "thermal_drift"

    def test_returns_to_normal_after_fault_duration(self):
        e = DegradationEngine("arm_01")
        e._fault_at = 1
        e._fault_duration = 3  # active during steps 1, 2, 3
        e.step = 0
        with patch.object(random, "choice", return_value="vibration_spike"):
            e.tick()  # step=1 → fault starts
        assert e.mode == "vibration_spike"
        e.tick()  # step=2
        e.tick()  # step=3
        e.tick()  # step=4 → outside [1,4) → returns to normal
        assert e.mode == "normal"

    def test_reschedules_after_recovery(self):
        e = DegradationEngine("arm_01")
        e._fault_at = 1
        e._fault_duration = 1
        e.step = 0
        with patch.object(random, "choice", return_value="overcurrent"):
            e.tick()  # step=1, fault active
        e.tick()  # step=2, fault over → reschedule
        assert e.mode == "normal"
        # New fault_at should be relative to current step
        assert e._fault_at > e.step


# ---------------------------------------------------------------------------
# thermal_drift
# ---------------------------------------------------------------------------

class TestThermalDrift:
    def test_temperature_increases_proportionally(self):
        e = _engine_at_fault(mode="thermal_drift", step=50, fault_at=0, duration=100)
        # progress = 50/100 = 0.5 → +30 * 0.5 = +15
        assert abs(e.apply("temperature", 60.0) - 75.0) < 1e-9

    def test_temperature_at_full_progress(self):
        e = _engine_at_fault(mode="thermal_drift", step=100, fault_at=0, duration=100)
        # progress = 1.0 → +30
        assert abs(e.apply("temperature", 60.0) - 90.0) < 1e-9

    def test_does_not_affect_vibration(self):
        e = _engine_at_fault(mode="thermal_drift", step=50)
        assert e.apply("vibration", 1.5) == 1.5

    def test_does_not_affect_current(self):
        e = _engine_at_fault(mode="thermal_drift", step=50)
        assert e.apply("current", 5.0) == 5.0


# ---------------------------------------------------------------------------
# vibration_spike
# ---------------------------------------------------------------------------

class TestVibrationSpike:
    def test_vibration_oscillates(self):
        e = _engine_at_fault(mode="vibration_spike", step=25, fault_at=0, duration=100)
        progress = 0.25
        expected = 1.5 + 8.0 * abs(math.sin(progress * math.pi * 4))
        assert abs(e.apply("vibration", 1.5) - expected) < 1e-9

    def test_spike_is_non_negative(self):
        for step in [0, 10, 25, 50, 75, 99]:
            e = _engine_at_fault(mode="vibration_spike", step=step, fault_at=0, duration=100)
            result = e.apply("vibration", 0.5)
            assert result >= 0.5  # spike only adds, never subtracts

    def test_does_not_affect_temperature(self):
        e = _engine_at_fault(mode="vibration_spike", step=25)
        assert e.apply("temperature", 60.0) == 60.0

    def test_does_not_affect_current(self):
        e = _engine_at_fault(mode="vibration_spike", step=25)
        assert e.apply("current", 5.0) == 5.0


# ---------------------------------------------------------------------------
# overcurrent
# ---------------------------------------------------------------------------

class TestOvercurrent:
    def test_current_increases_gradually(self):
        e = _engine_at_fault(mode="overcurrent", step=10, fault_at=0, duration=100)
        # progress = 0.10, progress*3 = 0.30 → +6*0.30 = +1.8
        expected = 5.0 + 6.0 * min(0.10 * 3, 1.0)
        assert abs(e.apply("current", 5.0) - expected) < 1e-9

    def test_current_caps_at_plus_six(self):
        e = _engine_at_fault(mode="overcurrent", step=50, fault_at=0, duration=100)
        # progress=0.5, progress*3=1.5 → clamped to 1.0 → +6
        assert abs(e.apply("current", 5.0) - 11.0) < 1e-9

    def test_does_not_affect_temperature(self):
        e = _engine_at_fault(mode="overcurrent", step=50)
        assert e.apply("temperature", 60.0) == 60.0

    def test_does_not_affect_vibration(self):
        e = _engine_at_fault(mode="overcurrent", step=50)
        assert e.apply("vibration", 1.5) == 1.5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_fault_duration_no_division_by_zero(self):
        e = _engine_at_fault(mode="thermal_drift", step=5, fault_at=0, duration=0)
        # max(0, 1) prevents ZeroDivisionError
        result = e.apply("temperature", 60.0)
        assert isinstance(result, float)

    def test_unknown_sensor_in_fault_returns_base(self):
        e = _engine_at_fault(mode="thermal_drift", step=50)
        assert e.apply("pressure", 100.0) == 100.0

    def test_fault_active_boundaries(self):
        e = DegradationEngine("arm_01")
        e._fault_at = 10
        e._fault_duration = 5  # active: 10, 11, 12, 13, 14
        e.step = 9
        assert not e._fault_active()
        e.step = 10
        assert e._fault_active()
        e.step = 14
        assert e._fault_active()
        e.step = 15
        assert not e._fault_active()
