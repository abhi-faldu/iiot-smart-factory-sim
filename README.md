# IIoT Smart Factory Simulator

An Industry 4.0 IIoT simulator: three robotic arms publish live sensor data over MQTT, a real-time Z-score anomaly detector flags faults, all data lands in InfluxDB, and a pre-provisioned Grafana dashboard visualises everything — fully Dockerized.

---

## Architecture

```
[Simulator]  →  MQTT (Mosquitto)  →  [Detector]  →  InfluxDB  →  Grafana
  3 robot arms                         Z-score                    live dashboard
  temperature                          anomaly flag
  vibration                            per arm/sensor
  current
```

### Services

| Service | Image | Port |
|---|---|---|
| mosquitto | eclipse-mosquitto:2.0 | 1883 |
| influxdb | influxdb:2.7 | 8086 |
| simulator | custom (python:3.11-slim) | — |
| detector | custom (python:3.11-slim) | — |
| grafana | grafana/grafana:10.4.2 | 3000 |

---

## Quick Start

```bash
git clone https://github.com/abhi-faldu/iiot-smart-factory-sim.git
cd iiot-smart-factory-sim
docker compose up --build
```

Open Grafana at **http://localhost:3000** (admin / admin).  
The *IIoT Smart Factory* dashboard loads automatically.

---

## Simulator

- Publishes every **1 second** to `factory/robot/<arm_id>/<sensor>`
- Three arms: `arm_01`, `arm_02`, `arm_03`
- Three sensors per arm: `temperature`, `vibration`, `current`
- Payload: `{ "ts", "arm_id", "sensor", "value", "mode" }`

### Fault Injection (`degradation.py`)

Each arm independently cycles through fault modes on a random schedule (every 60–180 cycles):

| Mode | Affected sensor | Pattern |
|---|---|---|
| `thermal_drift` | temperature | Gradual +30 °C ramp |
| `vibration_spike` | vibration | Oscillating +8 g burst |
| `overcurrent` | current | Step increase of +6 A |

---

## Anomaly Detector

- Subscribes to `factory/robot/#`
- Maintains a **30-sample sliding window** per (arm, sensor) pair
- Flags anomaly when **Z-score > 3.0**
- Writes every reading (value, z\_score, mean, std, is\_anomaly) to InfluxDB

---

## Grafana Dashboard

Pre-provisioned panels:

- Temperature per arm (time-series)
- Vibration per arm (time-series)
- Current per arm (time-series)
- Z-score over time with threshold line at 3.0
- Current anomaly status per arm/sensor (stat panel, green/red)

Refreshes every **5 seconds**, default window **last 15 minutes**.

---

## Project Structure

```
iiot-smart-factory-sim/
├── broker/
│   └── mosquitto.conf
├── simulator/
│   ├── config.py
│   ├── degradation.py
│   └── publisher.py
├── detector/
│   ├── zscore_detector.py
│   ├── influx_writer.py
│   └── subscriber.py
├── grafana/
│   └── provisioning/
│       ├── datasources/influxdb.yml
│       └── dashboards/
│           ├── dashboard.yml
│           └── factory_dashboard.json
├── Dockerfile.simulator
├── Dockerfile.detector
├── docker-compose.yml
└── requirements.txt
```

---

## Stack

Python 3.11 · Paho-MQTT · InfluxDB 2.7 (Flux) · Grafana 10 · Mosquitto 2 · Docker Compose
