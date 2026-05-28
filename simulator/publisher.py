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
    SENSOR_BASELINES,
    SENSOR_NOISE_STD,
    SENSORS,
    TOPIC_TEMPLATE,
)
from degradation import DegradationEngine


def _base_value(sensor: str) -> float:
    return SENSOR_BASELINES[sensor]


def _add_noise(sensor: str, value: float) -> float:
    return value + random.gauss(0, SENSOR_NOISE_STD[sensor])


def _on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[simulator] unexpected disconnect rc={rc}; auto-reconnecting")


def _connect_with_retry(client):
    """Block until the broker accepts a connection, backing off between tries."""
    delay = 1
    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            return
        except OSError as exc:
            print(f"[simulator] broker unavailable ({exc}); retrying in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main():
    client = mqtt.Client(client_id="factory-simulator")
    client.on_disconnect = _on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    _connect_with_retry(client)
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
                value = round(_add_noise(sensor, degraded), 4)

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
