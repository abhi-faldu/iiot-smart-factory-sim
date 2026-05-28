"""
Replay the AI4I 2020 Predictive Maintenance dataset into the MQTT pipeline.

Download the dataset from:
  https://www.kaggle.com/datasets/stephanmatzka/predictive-maintenance-dataset-ai4i-2020
Save the CSV as: data/ai4i2020.csv

Usage:
  python replay.py data/ai4i2020.csv
  python replay.py data/ai4i2020.csv --delay 0.2   # faster replay
  python replay.py data/ai4i2020.csv --failures-only  # only rows with a fault
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
TOPIC_TEMPLATE = "factory/robot/{arm_id}/{sensor}"

# AI4I product type → robot arm
TYPE_TO_ARM = {"L": "arm_01", "M": "arm_02", "H": "arm_03"}

# AI4I column → our sensor name
COLUMN_MAP = {
    "temperature": "Air temperature [K]",
    "vibration":   "Rotational speed [rpm]",
    "current":     "Torque [Nm]",
}

# Failure type columns in the dataset
FAILURE_COLS = ["TWF", "HDF", "PWF", "OSF", "RNF"]


def _convert(sensor: str, raw: str) -> float:
    v = float(raw)
    if sensor == "temperature":
        return round(v - 273.15, 2)   # Kelvin → °C
    if sensor == "vibration":
        return round(v / 1000.0, 4)   # rpm → g proxy
    if sensor == "current":
        return round(v / 6.0, 4)      # Nm → A proxy
    return round(v, 4)


def _failure_label(row: dict) -> str:
    for col in FAILURE_COLS:
        if int(row.get(col, 0)):
            return col
    return "normal"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", help="Path to ai4i2020.csv")
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds between rows (default: 1.0)"
    )
    parser.add_argument(
        "--failures-only", action="store_true",
        help="Only publish rows where Machine failure = 1"
    )
    args = parser.parse_args()

    client = mqtt.Client(client_id="dataset-replay")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    print(f"[replay] connected → {BROKER_HOST}:{BROKER_PORT}")
    print(f"[replay] delay={args.delay}s  failures-only={args.failures_only}")
    print()

    with open(args.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            machine_failure = int(row.get("Machine failure", 0))

            if args.failures_only and not machine_failure:
                continue

            arm_id = TYPE_TO_ARM.get(row.get("Type", "L"), "arm_01")
            mode = _failure_label(row)
            ts = datetime.now(timezone.utc).isoformat()

            for sensor, col in COLUMN_MAP.items():
                value = _convert(sensor, row[col])
                topic = TOPIC_TEMPLATE.format(arm_id=arm_id, sensor=sensor)
                payload = json.dumps({
                    "ts": ts,
                    "arm_id": arm_id,
                    "sensor": sensor,
                    "value": value,
                    "mode": mode,
                })
                client.publish(topic, payload, qos=1)

            temp = _convert("temperature", row[COLUMN_MAP["temperature"]])
            vib  = _convert("vibration",   row[COLUMN_MAP["vibration"]])
            curr = _convert("current",     row[COLUMN_MAP["current"]])
            flag = f"  *** FAULT: {mode} ***" if machine_failure else ""
            print(
                f"[row {i+1:05d}] {arm_id}  "
                f"temp={temp:6.1f}°C  vib={vib:.3f}g  curr={curr:.2f}A"
                f"{flag}"
            )

            time.sleep(args.delay)

    print("\n[replay] finished")
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
