"""Unit tests for ZScoreDetector — TDD RED gate."""
import pytest

from zscore_detector import ZScoreDetector


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_window_size(self):
        d = ZScoreDetector()
        assert d.window_size == 30

    def test_default_threshold(self):
        d = ZScoreDetector()
        assert d.threshold == 3.0

    def test_custom_params(self):
        d = ZScoreDetector(window_size=10, threshold=2.5)
        assert d.window_size == 10
        assert d.threshold == 2.5

    def test_no_windows_on_init(self):
        d = ZScoreDetector()
        assert len(d._windows) == 0


# ---------------------------------------------------------------------------
# Insufficient data (< 10 samples)
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_no_anomaly_on_first_sample(self):
        d = ZScoreDetector()
        result = d.update("arm_01", "temperature", 60.0)
        assert result["is_anomaly"] is False

    def test_z_score_zero_with_insufficient_data(self):
        d = ZScoreDetector()
        for _ in range(9):
            result = d.update("arm_01", "temperature", 60.0)
        assert result["z_score"] == 0.0

    def test_mean_equals_current_value_with_insufficient_data(self):
        d = ZScoreDetector()
        result = d.update("arm_01", "temperature", 55.0)
        assert result["mean"] == 55.0

    def test_std_zero_with_insufficient_data(self):
        d = ZScoreDetector()
        result = d.update("arm_01", "temperature", 55.0)
        assert result["std"] == 0.0

    def test_threshold_at_exactly_10_samples(self):
        d = ZScoreDetector(window_size=30, threshold=3.0)
        for _ in range(9):
            d.update("arm_01", "temperature", 60.0)
        # 10th sample — now has enough data
        result = d.update("arm_01", "temperature", 60.0)
        # Stable constant data → z_score = 0
        assert result["z_score"] == 0.0


# ---------------------------------------------------------------------------
# Stable data / no anomaly
# ---------------------------------------------------------------------------

class TestStableData:
    def test_constant_values_give_zero_z_score(self):
        d = ZScoreDetector()
        for _ in range(25):
            result = d.update("arm_01", "temperature", 60.0)
        assert result["z_score"] == 0.0
        assert result["is_anomaly"] is False

    def test_small_variation_not_flagged(self):
        import random as rng
        rng.seed(42)
        d = ZScoreDetector(threshold=3.0)
        for _ in range(25):
            d.update("arm_01", "temperature", 60.0 + rng.gauss(0, 0.5))
        result = d.update("arm_01", "temperature", 61.0)
        assert result["is_anomaly"] is False


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class TestAnomalyDetection:
    def test_large_spike_detected(self):
        d = ZScoreDetector(threshold=3.0)
        for _ in range(25):
            d.update("arm_01", "temperature", 60.0)
        result = d.update("arm_01", "temperature", 300.0)
        assert result["is_anomaly"] is True
        assert result["z_score"] > 3.0

    def test_sensitive_threshold_catches_smaller_deviation(self):
        d = ZScoreDetector(window_size=30, threshold=1.0)
        for _ in range(20):
            d.update("arm_01", "temperature", 60.0)
        result = d.update("arm_01", "temperature", 90.0)
        assert result["is_anomaly"] is True

    def test_anomaly_flag_is_boolean(self):
        d = ZScoreDetector()
        result = d.update("arm_01", "temperature", 60.0)
        assert isinstance(result["is_anomaly"], bool)


# ---------------------------------------------------------------------------
# Window isolation
# ---------------------------------------------------------------------------

class TestWindowIsolation:
    def test_separate_window_per_arm(self):
        d = ZScoreDetector()
        for _ in range(20):
            d.update("arm_01", "temperature", 60.0)
        # arm_02 starts fresh — only 1 sample
        result = d.update("arm_02", "temperature", 60.0)
        assert result["z_score"] == 0.0
        assert result["is_anomaly"] is False

    def test_separate_window_per_sensor(self):
        d = ZScoreDetector()
        for _ in range(20):
            d.update("arm_01", "temperature", 60.0)
        result = d.update("arm_01", "vibration", 1.5)
        assert result["z_score"] == 0.0

    def test_window_size_bounded(self):
        d = ZScoreDetector(window_size=10)
        for i in range(100):
            d.update("arm_01", "temperature", float(i))
        window = d._get_window("arm_01", "temperature")
        assert len(window) == 10

    def test_old_values_evicted_from_window(self):
        d = ZScoreDetector(window_size=5)
        for i in range(5):
            d.update("arm_01", "temperature", float(i))
        # Push one more — oldest (0.0) should be gone
        d.update("arm_01", "temperature", 10.0)
        window = d._get_window("arm_01", "temperature")
        assert 0.0 not in window


# ---------------------------------------------------------------------------
# Return shape and rounding
# ---------------------------------------------------------------------------

class TestReturnShape:
    def test_all_keys_present(self):
        d = ZScoreDetector()
        for _ in range(15):
            result = d.update("arm_01", "temperature", 60.0)
        assert set(result.keys()) == {"z_score", "is_anomaly", "mean", "std"}

    def test_z_score_rounded_to_4dp(self):
        d = ZScoreDetector()
        for i in range(20):
            d.update("arm_01", "temperature", float(i))
        result = d.update("arm_01", "temperature", 100.0)
        z = result["z_score"]
        assert z == round(z, 4)

    def test_mean_rounded_to_4dp(self):
        d = ZScoreDetector()
        for _ in range(15):
            result = d.update("arm_01", "temperature", 60.12345)
        mean = result["mean"]
        assert mean == round(mean, 4)

    def test_std_zero_for_constant_input(self):
        d = ZScoreDetector()
        for _ in range(20):
            result = d.update("arm_01", "temperature", 42.0)
        assert result["std"] == 0.0
        assert result["z_score"] == 0.0
