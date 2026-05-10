import os

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")   # was influxdb
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "factory-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "factory")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "sensors")


class InfluxWriter:
    def __init__(self):
        self._client = InfluxDBClient(
            url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG
        )
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write(
        self,
        arm_id: str,
        sensor: str,
        value: float,
        z_score: float,
        is_anomaly: bool,
        mean: float,
        std: float,
        mode: str,
    ):
        point = (
            Point("sensor_reading")
            .tag("arm_id", arm_id)
            .tag("sensor", sensor)
            .tag("fault_mode", mode)
            .field("value", value)
            .field("z_score", z_score)
            .field("mean", mean)
            .field("std", std)
            .field("is_anomaly", int(is_anomaly))
        )
        self._write_api.write(
            bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point,
            write_precision=WritePrecision.S,
        )

    def close(self):
        self._client.close()
