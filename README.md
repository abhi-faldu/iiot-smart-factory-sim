<div style="text-align:center">

# ⚙️ iiot-smart-factory-sim

**End-to-end Industry 4.0 IIoT simulator for real-time sensor monitoring and anomaly detection**  
**using MQTT, Z-score detection, InfluxDB, and a live Grafana + custom web dashboard**

[![License: MIT](https://img.shields.io/badge/LICENSE-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=flat-square&logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org)
[![InfluxDB](https://img.shields.io/badge/DB-InfluxDB_2.7-22ADF6?style=flat-square&logo=influxdb&logoColor=white)](https://influxdata.com)
[![Grafana](https://img.shields.io/badge/VIZ-Grafana-F46800?style=flat-square&logo=grafana&logoColor=white)](https://grafana.com)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/CONTAINER-Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

[Quick Start](#-quickstart) · [Architecture](#-architecture) · [Sensors](#-sensor-configuration) · [Anomaly Detection](#-anomaly-detection) · [Dashboard](#-dashboard) · [API](#-api-usage) · [Docker](#-docker)

</div>

---

## Problem 🏭

Modern automotive plants run hundreds of robotic arms continuously. Sensor data from each arm — temperature, vibration, motor current — streams at high frequency. A single undetected fault that escalates into mechanical failure can halt an entire assembly line, costing **€500,000+ per hour** in downtime.

This project simulates that IIoT environment end-to-end: three robotic arms publishing live sensor telemetry over MQTT, a real-time sliding-window Z-score detector flagging anomalies as they occur, a time-series database storing every reading, and a custom dark-theme dashboard visualising the full picture — all containerised and deployable with one command.

---

## What This Project Does 🎯

| Step | Description |
|------|-------------|
| **Simulate** | 3 robot arms publish temperature, vibration, and motor current over MQTT every second |
| **Inject** | Realistic fault patterns (thermal drift, vibration spike, overcurrent) injected on random schedules |
| **Detect** | Sliding-window Z-score detector (window=30, threshold=3.0σ) flags anomalies in real time |
| **Store** | Every reading + anomaly score written to InfluxDB 2.7 with tags for arm, sensor, fault mode |
| **Visualise** | Pre-provisioned Grafana dashboard + custom FastAPI-served HTML dashboard with interactive modals |
| **Serve** | FastAPI REST API — `/api/sensors/latest`, `/api/sensors/history`, `/api/anomalies` |
| **Deploy** | Docker Compose — 6 services, one command |

---

## Project Structure 🗂️

```text
iiot-smart-factory-sim/
├── broker/
│   └── mosquitto.conf              ← Mosquitto MQTT broker config (anon, persistent)
├── simulator/
│   ├── config.py                   ← Topics, arm IDs, sensor ranges, publish interval
│   ├── degradation.py              ← Fault injection engine (thermal drift, vib spike, overcurrent)
│   └── publisher.py                ← MQTT publisher — 3 arms × 3 sensors × 1s interval
├── detector/
│   ├── zscore_detector.py          ← Sliding-window Z-score anomaly detector (window=30)
│   ├── influx_writer.py            ← Writes readings + anomaly scores to InfluxDB
│   └── subscriber.py               ← MQTT consumer — runs detection, writes to InfluxDB
├── api/
│   └── main.py                     ← FastAPI backend serving dashboard + sensor data
├── frontend/
│   └── index.html                  ← Custom dark-theme dashboard (vanilla JS + Chart.js)
├── grafana/
│   └── provisioning/
│       ├── datasources/influxdb.yml ← InfluxDB datasource (pre-provisioned)
│       └── dashboards/             ← Factory dashboard JSON (auto-loaded)
├── findings/                       ← Anomaly detection plots + FINDINGS.md
├── replay.py                       ← Replay AI4I 2020 dataset into the pipeline
├── Dockerfile.simulator
├── Dockerfile.detector
├── Dockerfile.api
├── docker-compose.yml
└── requirements.txt
```

---

## Architecture 🔌

![Architecture diagram: Docker Compose stack with six services. Simulator (3 arms, 9 channels) publishes via MQTT pub/sub to Mosquitto Broker on port 1883. Detector subscribes over HTTP, runs Z-score anomaly detection, and writes results to InfluxDB on port 8086. FastAPI on port 8000 queries InfluxDB via Flux and serves a Browser Dashboard over REST/JSON. Grafana on port 3000 also queries InfluxDB directly.](findings/architecture_readme.png)

### Services

| Service | Image | Port | Role |
|---|---|---|---|
| mosquitto | eclipse-mosquitto:2.0 | 1883 | MQTT broker |
| influxdb | influxdb:2.7 | 8086 | Time-series storage |
| simulator | custom python:3.11-slim | — | Sensor data publisher |
| detector | custom python:3.11-slim | — | Z-score detector + InfluxDB writer |
| api | custom python:3.11-slim | 8000 | Dashboard + REST API |
| grafana | grafana/grafana:10.4.2 | 3000 | Pre-provisioned monitoring dashboard |

---

## Sensor Configuration 📡

Three robot arms (`arm_01`, `arm_02`, `arm_03`), each publishing three sensors every second to `factory/robot/<arm_id>/<sensor>`:

| Sensor | Unit | Normal Range | MQTT Topic |
|---|---|---|---|
| Temperature | °C | 40 – 85 | `factory/robot/arm_01/temperature` |
| Vibration | g | 0.1 – 3.0 | `factory/robot/arm_01/vibration` |
| Motor Current | A | 2.0 – 10.0 | `factory/robot/arm_01/current` |

### MQTT Payload

```json
{
  "ts": "2026-05-10T17:35:00.123456+00:00",
  "arm_id": "arm_01",
  "sensor": "temperature",
  "value": 63.4,
  "mode": "normal"
}
```

---

## Anomaly Detection 🧠

### Z-Score Sliding Window

```text
For each (arm_id, sensor) pair:

  window  =  last 30 readings  [ring buffer]
  mean    =  mean(window)
  std     =  std(window)

  z_score =  |value − mean| / std

  anomaly =  z_score > 3.0
```

**Why Z-score over ML here?** This project deliberately uses a lightweight statistical method to show that Industry 4.0 does not always require a neural network. Z-score runs in microseconds per reading, requires no training data, and adapts automatically as the window slides forward. For the complementary deep-learning approach, see [`robotic-bearing-pdm`](https://github.com/abhi-faldu/robotic-bearing-pdm).

### Fault Injection — `degradation.py`

Each arm independently cycles through fault modes on a random schedule (every 60–180 publish cycles):

| Fault Mode | Affected Sensor | Pattern | Severity |
|---|---|---|---|
| `THERMAL_DRIFT` | Temperature | Gradual ramp +10 to +30 °C | Medium → High |
| `VIBRATION_SPIKE` | Vibration | Oscillating +8 g burst | High |
| `OVERCURRENT` | Motor Current | Step increase +6 A | Medium |

Faults last 20–60 cycles (~20–60 seconds), then the arm returns to normal. The Z-score detector must distinguish real faults from sensor noise using only the rolling statistics — no labels, no prior knowledge of fault types.

---

## Quickstart 🚀

### Option A — Full Docker Stack (recommended)

```bash
git clone https://github.com/abhi-faldu/iiot-smart-factory-sim.git
cd iiot-smart-factory-sim
docker compose up --build
```

| Service | URL |
|---|---|
| Custom dashboard | http://localhost:8000 |
| Grafana | http://localhost:3000 |
| InfluxDB | http://localhost:8086 |
| FastAPI docs | http://localhost:8000/docs |

> Data starts flowing within 5–10 seconds. Fault events appear within ~60–180 seconds.

---

### Option B — Local Python (for development)

```bash
# 1 — Infrastructure only
docker compose up mosquitto influxdb

# 2 — Install dependencies
pip install -r requirements.txt

# 3 — Detector first (subscribe before publishing)
cd detector && python subscriber.py

# 4 — Simulator (new terminal)
cd simulator && python publisher.py

# 5 — API + dashboard (new terminal)
cd api && uvicorn main:app --port 8000
```

Open **http://localhost:8000** — dashboard switches from simulator feed to live API automatically.

---

### Option C — Replay Public Dataset (AI4I 2020)

Test alert functionality with real labeled fault data:

```bash
# Download: kaggle datasets download stephanmatzka/predictive-maintenance-dataset-ai4i-2020
# Save as: data/ai4i2020.csv

python replay.py data/ai4i2020.csv --delay 0.2      # fast replay
python replay.py data/ai4i2020.csv --failures-only  # only fault rows
```

Dataset column mapping:

| AI4I Column | Sensor | Conversion |
|---|---|---|
| Air temperature [K] | temperature | K − 273.15 → °C |
| Rotational speed [rpm] | vibration | rpm / 1000 → g proxy |
| Torque [Nm] | current | Nm / 6 → A proxy |

---

## API Usage 🌐

```bash
# Latest reading for all arms
curl http://localhost:8000/api/sensors/latest

# 15-minute history
curl "http://localhost:8000/api/sensors/history?minutes=15"

# Anomaly events (last 1 hour)
curl http://localhost:8000/api/anomalies

# Health check
curl http://localhost:8000/health
```

**`/api/sensors/latest` response:**

```json
{
  "arm_01": { "temperature": 68.3, "vibration": 1.62, "current": 6.1, "fault_mode": "NORMAL", "ts": 1715362500000 },
  "arm_02": { "temperature": 71.2, "vibration": 1.51, "current": 7.4, "fault_mode": "THERMAL_DRIFT", "ts": 1715362500000 },
  "arm_03": { "temperature": 65.8, "vibration": 1.59, "current": 5.9, "fault_mode": "NORMAL", "ts": 1715362500000 }
}
```

**`/api/anomalies` response:**

```json
[
  {
    "ts": 1715362450000,
    "arm": "arm_02",
    "sensor": "temperature",
    "value": 96.4,
    "z": 4.21,
    "fault_mode": "THERMAL_DRIFT"
  }
]
```

---

## Dashboard 📊

### Custom Web Dashboard (http://localhost:8000)

Dark-theme single-page dashboard built with vanilla JS + Chart.js. Polls the FastAPI backend every 2 seconds. Falls back to an in-browser simulator feed when the API is offline (shows orange "SIM FEED" pill — useful for portfolio demos without a running backend).

**Features:**
- 3 arm status cards with live fault mode badges (NORMAL / THERMAL DRIFT / VIBRATION SPIKE / OVERCURRENT)
- Per-card sensor metric tiles — click any tile to open the **interactive sensor detail modal**
- 3 stacked time-series charts (Temperature / Vibration / Current), one line per arm
- Z-score anomaly chart with ±3.0σ dashed threshold and red anomaly dot overlay
- Scrollable anomaly event log with timestamps, Z-scores, and fault mode labels

**Interactive Sensor Modal** — click any metric tile to open:
- Live reading with 5-minute min / avg / max statistics
- Z-score gauge bar (green → orange → red)
- Zoomed 5-minute mini chart with anomaly dot markers
- Fault-mode-aware diagnostic recommendations (4 action items)
- Last 8 anomaly events for that specific arm/sensor

### Grafana Dashboard (http://localhost:3000)

Pre-provisioned at startup via `grafana/provisioning/`. No manual setup required.

---

## Docker 🐳

```bash
# Full stack
docker compose up --build

# Individual services
docker compose up mosquitto influxdb        # infrastructure only
docker compose up mosquitto influxdb api    # + dashboard

# Rebuild after code changes
docker compose up --build simulator detector api

# Stop and clean up
docker compose down
docker compose down -v   # also removes data volumes
```

---

## Tech Stack 🛠️

| Layer | Technology |
|---|---|
| Messaging | Paho-MQTT + Eclipse Mosquitto 2.0 |
| Detection | Custom sliding-window Z-score (NumPy) |
| Storage | InfluxDB 2.7 (Flux query language) |
| API | FastAPI 0.111 + Uvicorn 0.29 |
| Frontend | Vanilla JS + Chart.js 4.4 + JetBrains Mono |
| Monitoring | Grafana 10.4 (pre-provisioned) |
| Containerisation | Docker, Docker Compose |
| Dataset replay | AI4I 2020 Predictive Maintenance (Kaggle) |

---

## What's Built ✅

- [x] MQTT simulator — 3 robot arms × 3 sensors × 1s publish interval
- [x] Fault injection engine — thermal drift, vibration spike, overcurrent
- [x] Z-score anomaly detector — sliding window 30 samples, threshold 3.0σ
- [x] InfluxDB writer — sensor readings + anomaly scores + fault mode tags
- [x] FastAPI backend — 3 REST endpoints + health check + error handling
- [x] Custom dashboard — dark theme, 3 sensor charts, Z-score chart, anomaly log
- [x] Interactive sensor modal — live stats, mini chart, diagnostic recommendations
- [x] Grafana dashboard — pre-provisioned, auto-loads on `docker compose up`
- [x] AI4I 2020 dataset replay script — injects real fault data into the pipeline
- [x] Docker Compose — 6-service stack, InfluxDB health check, automatic restart

