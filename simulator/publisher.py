import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import (
    ARM_IDS,
    BROKER_HOST,
    BROKER_PORT,
    PUBLISH_INTERVAL,
    SENSOR_RANGES,
    SENSORS,
    TOPIC_TEMPLATE,
)
from degradation import DegradationEngine


def _base_value(sensor: str) -> float:
    r = SENSOR_RANGES[sensor]
    return random.uniform(r["min"], r["max"])


def _add_noise(value: float) -> float:
    return value + random.gauss(0, 0.05 * value)


def main():
    client = mqtt.Client(client_id="factory-simulator")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    engines = {arm_id: DegradationEngine(arm_id) for arm_id in ARM_IDS}

    print(f"[simulator] connected to {BROKER_HOST}:{BROKER_PORT}")

    while True:
        ts = datetime.now(timezone.utc).isoformat()

        for arm_id in ARM_IDS:
            engine = engines[arm_id]
            engine.tick()

            for sensor in SENSORS:
                raw = _base_value(sensor)
                degraded = engine.apply(sensor, raw)
                value = round(_add_noise(degraded), 4)

                topic = TOPIC_TEMPLATE.format(arm_id=arm_id, sensor=sensor)
                payload = json.dumps({
                    "ts": ts,
                    "arm_id": arm_id,
                    "sensor": sensor,
                    "value": value,
                    "mode": engine.mode,
                })
                client.publish(topic, payload, qos=1)

            print(f"[{ts}] {arm_id} | mode={engine.mode}")

        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()
