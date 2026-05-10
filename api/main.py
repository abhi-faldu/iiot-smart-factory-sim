import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from influxdb_client import InfluxDBClient

INFLUX_URL    = os.getenv("INFLUX_URL",    "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN",  "factory-token")
INFLUX_ORG    = os.getenv("INFLUX_ORG",    "factory")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "sensors")

ARM_IDS = ["arm_01", "arm_02", "arm_03"]
SENSORS = ["temperature", "vibration", "current"]

FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"

app = FastAPI(title="IIoT Smart Factory API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

client    = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()


def _pivot_query(start: str) -> str:
    return f"""
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start})
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> pivot(
       rowKey:["_time","arm_id","sensor","fault_mode"],
       columnKey:["_field"],
       valueColumn:"_value"
     )
"""


@app.get("/")
def serve_dashboard():
    return FileResponse(str(FRONTEND), media_type="text/html")


@app.get("/api/sensors/latest")
def get_latest():
    tables = query_api.query(_pivot_query("-2m"))

    # Keep only the most-recent record per (arm, sensor)
    best: dict[tuple, dict] = {}
    for table in tables:
        for rec in table.records:
            arm    = rec.values.get("arm_id")
            sensor = rec.values.get("sensor")
            if arm not in ARM_IDS or sensor not in SENSORS:
                continue
            key = (arm, sensor)
            ts  = rec.get_time()
            if key not in best or ts > best[key]["_ts"]:
                best[key] = {
                    "_ts":       ts,
                    "arm_id":    arm,
                    "sensor":    sensor,
                    "value":     rec.values.get("value"),
                    "fault_mode": (rec.values.get("fault_mode") or "normal").upper(),
                }

    result: dict[str, dict] = {arm: {"fault_mode": "NORMAL"} for arm in ARM_IDS}
    for (arm, sensor), row in best.items():
        result[arm][sensor]     = row["value"]
        result[arm]["fault_mode"] = row["fault_mode"]
        result[arm]["ts"]       = int(row["_ts"].timestamp() * 1000)

    return result


@app.get("/api/sensors/history")
def get_history(minutes: int = Query(15, ge=1, le=60)):
    tables = query_api.query(_pivot_query(f"-{minutes}m"))

    result: dict[str, dict] = {
        arm: {sensor: [] for sensor in SENSORS}
        for arm in ARM_IDS
    }
    for table in tables:
        for rec in table.records:
            arm    = rec.values.get("arm_id")
            sensor = rec.values.get("sensor")
            if arm not in result or sensor not in result[arm]:
                continue
            result[arm][sensor].append({
                "t": int(rec.get_time().timestamp() * 1000),
                "v": rec.values.get("value") or 0.0,
                "z": rec.values.get("z_score") or 0.0,
            })

    for arm in result:
        for sensor in result[arm]:
            result[arm][sensor].sort(key=lambda x: x["t"])

    return result


@app.get("/api/anomalies")
def get_anomalies():
    tables = query_api.query(_pivot_query("-1h"))

    anomalies = []
    for table in tables:
        for rec in table.records:
            if not rec.values.get("is_anomaly"):
                continue
            arm    = rec.values.get("arm_id")
            sensor = rec.values.get("sensor")
            if arm not in ARM_IDS or sensor not in SENSORS:
                continue
            anomalies.append({
                "ts":         int(rec.get_time().timestamp() * 1000),
                "arm":        arm,
                "sensor":     sensor,
                "value":      rec.values.get("value") or 0.0,
                "z":          rec.values.get("z_score") or 0.0,
                "fault_mode": (rec.values.get("fault_mode") or "normal").upper(),
            })

    anomalies.sort(key=lambda x: x["ts"], reverse=True)
    return anomalies[:200]
