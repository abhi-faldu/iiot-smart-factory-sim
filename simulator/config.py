import os

BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))

ARM_IDS = ["arm_01", "arm_02", "arm_03"]

PUBLISH_INTERVAL = 1.0  # seconds

# MQTT topic template: factory/robot/<arm_id>/<sensor>
TOPIC_TEMPLATE = "factory/robot/{arm_id}/{sensor}"

SENSORS = ["temperature", "vibration", "current"]

# Normal operating envelope per sensor (documents valid range, used for charts/validation)
SENSOR_RANGES = {
    "temperature": {"min": 40.0,  "max": 85.0},
    "vibration":   {"min": 0.1,   "max": 3.0},
    "current":     {"min": 2.0,   "max": 10.0},
}

# Stable operating baseline per sensor — the mean value under normal conditions.
# Readings vary around this by SENSOR_NOISE_STD, so faults stand out against a
# steady signal instead of being swamped by full-range uniform noise.
SENSOR_BASELINES = {
    "temperature": 62.5,   # °C
    "vibration":   1.55,   # g
    "current":     6.0,    # A
}

# Gaussian sensor noise (absolute standard deviation) added to each reading.
SENSOR_NOISE_STD = {
    "temperature": 1.0,    # °C  (~1.6% of baseline)
    "vibration":   0.05,   # g   (~3.2% of baseline)
    "current":     0.15,   # A   (~2.5% of baseline)
}
