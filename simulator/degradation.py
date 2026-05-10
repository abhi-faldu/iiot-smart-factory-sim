import random
import math


class DegradationEngine:
    """Injects realistic failure patterns into sensor readings for one robot arm."""

    MODES = ["normal", "thermal_drift", "vibration_spike", "overcurrent"]

    def __init__(self, arm_id: str):
        self.arm_id = arm_id
        self.mode = "normal"
        self.step = 0
        self._schedule_next_fault()

    def _schedule_next_fault(self):
        # Next fault triggers after 60–180 publish cycles
        self._fault_at = self.step + random.randint(60, 180)
        self._fault_duration = random.randint(20, 60)

    def _fault_active(self) -> bool:
        return self.step >= self._fault_at and self.step < self._fault_at + self._fault_duration

    def tick(self):
        """Advance one publish cycle. Call once per publish loop iteration."""
        self.step += 1
        if self._fault_active() and self.mode == "normal":
            self.mode = random.choice(["thermal_drift", "vibration_spike", "overcurrent"])
        elif not self._fault_active() and self.mode != "normal":
            self.mode = "normal"
            self._schedule_next_fault()

    def apply(self, sensor: str, base_value: float) -> float:
        """Return the (possibly degraded) sensor reading."""
        if self.mode == "normal":
            return base_value

        progress = (self.step - self._fault_at) / max(self._fault_duration, 1)

        if self.mode == "thermal_drift" and sensor == "temperature":
            # Gradual ramp up to +30 °C
            return base_value + 30.0 * progress

        if self.mode == "vibration_spike" and sensor == "vibration":
            # Oscillating spike peaking at +8 g
            return base_value + 8.0 * abs(math.sin(progress * math.pi * 4))

        if self.mode == "overcurrent" and sensor == "current":
            # Sudden step increase of +6 A
            return base_value + 6.0 * min(progress * 3, 1.0)

        return base_value
