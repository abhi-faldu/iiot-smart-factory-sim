import json
import signal
import sys

import paho.mqtt.client as mqtt

from influx_writer import InfluxWriter
from zscore_detector import ZScoreDetector

BROKER_HOST = "mosquitto"
BROKER_PORT = 1883
SUBSCRIBE_TOPIC = "factory/robot/#"

detector = ZScoreDetector(window_size=30, threshold=3.0)
writer = InfluxWriter()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(SUBSCRIBE_TOPIC, qos=1)
        print(f"[detector] subscribed to {SUBSCRIBE_TOPIC}")
    else:
        print(f"[detector] connection failed rc={rc}")


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
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    print(f"[detector] connecting to {BROKER_HOST}:{BROKER_PORT}")
    client.loop_forever()


if __name__ == "__main__":
    main()
