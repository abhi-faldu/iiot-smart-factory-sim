"""End-to-end pipeline test: simulator output → detector.

Guards the invariant that the simulator publishes around a *stable* baseline
with bounded noise, so injected faults stand out against the Z-score window.
A regression to full-range uniform sampling (the original bug) would bury the
fault signal and make this test fail — thermal_drift and overcurrent dropped to
~1% / ~6% per-episode detection in that broken state.
"""
import random
from collections import Counter

import pytest

import config
from degradation import DegradationEngine
from publisher import _add_noise, _base_value
from zscore_detector import ZScoreDetector

# Which sensor each fault mode actually perturbs.
FAULT_SENSOR = {
    "thermal_drift": "temperature",
    "vibration_spike": "vibration",
    "overcurrent": "current",
}


def _run_pipeline(seed, steps=5000):
    """Drive one arm through the full chain and tally per-episode detections."""
    random.seed(seed)
    detector = ZScoreDetector(window_size=30, threshold=3.0)
    engine = DegradationEngine("arm_01")

    episodes = []          # [mode, detected?] one entry per fault episode
    current = None
    false_pos = 0
    normal_samples = 0

    for _ in range(steps):
        prev_mode = engine.mode
        engine.tick()
        for sensor in config.SENSORS:
            raw = _base_value(sensor)
            degraded = engine.apply(sensor, raw)
            value = round(_add_noise(sensor, degraded), 4)
            result = detector.update("arm_01", sensor, value)

            if engine.mode == "normal":
                normal_samples += 1
                if result["is_anomaly"]:
                    false_pos += 1
            elif sensor == FAULT_SENSOR.get(engine.mode):
                if engine.mode != prev_mode:        # new episode began
                    current = [engine.mode, False]
                    episodes.append(current)
                if current and result["is_anomaly"]:
                    current[1] = True

    return episodes, false_pos, normal_samples


def _aggregate(seeds):
    total = Counter()
    detected = Counter()
    fp = 0
    normal = 0
    for seed in seeds:
        episodes, false_pos, normal_samples = _run_pipeline(seed)
        fp += false_pos
        normal += normal_samples
        for mode, hit in episodes:
            total[mode] += 1
            if hit:
                detected[mode] += 1
    return total, detected, fp, normal


SEEDS = range(10)


@pytest.fixture(scope="module")
def stats():
    """Run the (slow) multi-seed simulation once and share it across tests."""
    total, detected, fp, normal = _aggregate(SEEDS)
    return total, detected, fp, normal


class TestEndToEndDetection:
    def test_all_fault_types_occur(self, stats):
        total, _, _, _ = stats
        for mode in FAULT_SENSOR:
            assert total[mode] > 0, f"no {mode} episodes generated to test"

    def test_thermal_drift_detected(self, stats):
        total, detected, _, _ = stats
        rate = detected["thermal_drift"] / total["thermal_drift"]
        # Gradual ramp is the hardest case; was ~1% under the uniform-range bug.
        assert rate >= 0.5, f"thermal_drift per-episode detection too low: {rate:.0%}"

    def test_vibration_spike_detected(self, stats):
        total, detected, _, _ = stats
        rate = detected["vibration_spike"] / total["vibration_spike"]
        assert rate >= 0.9, f"vibration_spike per-episode detection too low: {rate:.0%}"

    def test_overcurrent_detected(self, stats):
        total, detected, _, _ = stats
        rate = detected["overcurrent"] / total["overcurrent"]
        # Was ~6% under the uniform-range bug.
        assert rate >= 0.9, f"overcurrent per-episode detection too low: {rate:.0%}"

    def test_false_positive_rate_low(self, stats):
        _, _, fp, normal = stats
        rate = fp / normal
        assert rate < 0.02, f"false-positive rate too high during normal operation: {rate:.2%}"
