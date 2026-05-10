BROKER_HOST = "mosquitto"
BROKER_PORT = 1883

ARM_IDS = ["arm_01", "arm_02", "arm_03"]

PUBLISH_INTERVAL = 1.0  # seconds

# MQTT topic template: factory/robot/<arm_id>/<sensor>
TOPIC_TEMPLATE = "factory/robot/{arm_id}/{sensor}"

SENSORS = ["temperature", "vibration", "current"]

# Normal operating ranges per sensor
SENSOR_RANGES = {
    "temperature": {"min": 40.0,  "max": 85.0},
    "vibration":   {"min": 0.1,   "max": 3.0},
    "current":     {"min": 2.0,   "max": 10.0},
}
