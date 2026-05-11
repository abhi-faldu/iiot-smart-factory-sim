# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Tests
```bash
# Run full test suite with coverage
.venv/Scripts/python -m pytest tests/

# Run a single test class or method
.venv/Scripts/python -m pytest tests/test_degradation.py::TestThermalDrift -v
.venv/Scripts/python -m pytest tests/test_api.py::TestGetLatest::test_sensor_value_returned -v

# Coverage only (no -v noise)
.venv/Scripts/python -m pytest tests/ --no-header -q
```

### Local development (no Docker)
```bash
# 1 — infrastructure
docker compose up mosquitto influxdb

# 2 — detector (must start before simulator so it subscribes first)
cd detector && python subscriber.py

# 3 — simulator
cd simulator && python publisher.py

# 4 — API + dashboard
cd api && uvicorn main:app --port 8000
```

### Full Docker stack
```bash
cp .env.example .env   # fill in real values first
docker compose up --build
```

### Dataset replay (AI4I 2020)
```bash
# Download from Kaggle, save as data/ai4i2020.csv, then:
python replay.py data/ai4i2020.csv --delay 0.2
python replay.py data/ai4i2020.csv --failures-only
```

## Architecture

### Data flow
```
simulator/ ──MQTT──► Mosquitto ──MQTT──► detector/
                                              │ write
                                         InfluxDB
                                              │ Flux query
                              browser ◄─ FastAPI (api/)
                              Grafana ◄─────────────────
```

### Module responsibilities

**`simulator/`** — Publishes synthetic telemetry. `DegradationEngine` (`degradation.py`) injects fault patterns into base readings; `publisher.py` applies noise and sends to `factory/robot/<arm_id>/<sensor>`. Config lives in `config.py` (broker host, sensor ranges, ARM_IDS).

**`detector/`** — `subscriber.py` consumes all MQTT messages, passes each reading through `ZScoreDetector`, then writes results to InfluxDB via `InfluxWriter`. Imports are bare names (`from zscore_detector import ...`) — must run from the `detector/` directory or have it on `sys.path`.

**`api/`** — FastAPI app with three endpoints plus a `/health` check. All three data endpoints call a single `_pivot_query()` helper that uses InfluxDB's Flux `pivot()` to reshape tag/field data into flat rows. Serves `frontend/index.html` at `/`.

**`frontend/index.html`** — Self-contained vanilla JS + Chart.js SPA. Polls the API every 2 s. When the API is unreachable it silently switches to a full in-browser simulator (Box-Muller noise, fault injection, rolling Z-score) so the dashboard works for portfolio demos without a running backend. The connection state is shown via the pill in the header.

### Key invariants

- **`INFLUX_TOKEN` must be set** — `api/main.py` calls `sys.exit(1)` at import time if missing. Tests set it via `tests/conftest.py` (`os.environ.setdefault("INFLUX_TOKEN", "test-token")`).
- **Detector startup order matters** — the detector must subscribe before the simulator publishes, otherwise early messages are lost.
- **Z-score warm-up** — `ZScoreDetector.update()` returns `is_anomaly=False` for the first 9 samples (window < 10). Expect a brief warm-up period after restart.
- **Docker vs local broker host** — `subscriber.py` and `simulator/config.py` use `"localhost"` for local dev. Inside Docker Compose the hostname is `"mosquitto"` — set via environment rather than hard-coding.
- **replay.py column mapping** — AI4I dataset uses Kelvin, rpm, and Nm; `replay.py` converts to °C, g-proxy, and A-proxy before publishing. Product type L/M/H maps to arm_01/02/03.

### Test layout

```
tests/
├── conftest.py          # sys.path wiring + INFLUX_TOKEN env stub
├── test_degradation.py  # DegradationEngine unit tests (100% coverage)
├── test_zscore_detector.py  # ZScoreDetector unit tests (100% coverage)
└── test_api.py          # FastAPI integration tests — InfluxDB mocked via
                         # monkeypatch on main.query_api (96% coverage)
```
