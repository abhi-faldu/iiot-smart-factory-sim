from collections import deque

import numpy as np


class ZScoreDetector:
    """Per-sensor sliding-window Z-score anomaly detector."""

    def __init__(self, window_size: int = 30, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        # key: (arm_id, sensor) → deque of recent values
        self._windows: dict[tuple, deque] = {}

    def _get_window(self, arm_id: str, sensor: str) -> deque:
        key = (arm_id, sensor)
        if key not in self._windows:
            self._windows[key] = deque(maxlen=self.window_size)
        return self._windows[key]

    def update(self, arm_id: str, sensor: str, value: float) -> dict:
        """
        Add value to the window and return anomaly info.
        Returns a dict with keys: z_score, is_anomaly, mean, std.
        """
        window = self._get_window(arm_id, sensor)
        window.append(value)

        if len(window) < 10:
            # Not enough data yet
            return {"z_score": 0.0, "is_anomaly": False, "mean": value, "std": 0.0}

        arr = np.array(window)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std < 1e-6:
            z_score = 0.0
        else:
            z_score = abs((value - mean) / std)

        return {
            "z_score": round(z_score, 4),
            "is_anomaly": z_score > self.threshold,
            "mean": round(mean, 4),
            "std": round(std, 4),
        }
