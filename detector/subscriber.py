import json
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt

from influx_writer import InfluxWriter
from zscore_detector import ZScoreDetector

BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
SUBSCRIBE_TOPIC = "factory/robot/#"

detector = ZScoreDetector(window_size=30, threshold=3.0)
writer = InfluxWriter()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        # Re-subscribe on every (re)connect so a dropped link recovers cleanly.
        client.subscribe(SUBSCRIBE_TOPIC, qos=1)
        print(f"[detector] subscribed to {SUBSCRIBE_TOPIC}")
    else:
        print(f"[detector] connection failed rc={rc}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[detector] unexpected disconnect rc={rc}; auto-reconnecting")


def _connect_with_retry(client):
    """Block until the broker accepts a connection, backing off between tries."""
    delay = 1
    while True:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            return
        except OSError as exc:
            print(f"[detector] broker unavailable ({exc}); retrying in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 30)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    arm_id = data.get("arm_id")
    sensor = data.get("sensor")
    value = data.get("value")
    mode = data.get("mode", "normal")

    if arm_id is None or sensor is None or value is None:
        return

    result = detector.update(arm_id, sensor, float(value))

    writer.write(
        arm_id=arm_id,
        sensor=sensor,
        value=float(value),
        z_score=result["z_score"],
        is_anomaly=result["is_anomaly"],
        mean=result["mean"],
        std=result["std"],
        mode=mode,
    )

    if result["is_anomaly"]:
        print(
            f"[ANOMALY] {arm_id}/{sensor} value={value} z={result['z_score']} mode={mode}"
        )


def _shutdown(sig, frame):
    print("[detector] shutting down")
    writer.close()
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    client = mqtt.Client(client_id="factory-detector")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    print(f"[detector] connecting to {BROKER_HOST}:{BROKER_PORT}")
    _connect_with_retry(client)
    client.loop_forever()


if __name__ == "__main__":
    main()
