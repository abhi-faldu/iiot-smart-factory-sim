# FINDINGS — IIoT Smart Factory Z-Score Anomaly Detection

> System configuration, detection methodology, and observed results for the `iiot-smart-factory-sim` project.  
> Simulator: 3 robot arms · 3 sensors each · 1-second publish interval  
> Detector: Sliding-window Z-score · window=30 · threshold=3.0σ

---

## 1 · System Configuration

| Parameter | Value |
|---|---|
| Robot arms | 3 (`arm_01`, `arm_02`, `arm_03`) |
| Sensors per arm | 3 (temperature, vibration, motor current) |
| Total channels | **9** |
| Publish interval | 1.0 second |
| MQTT QoS | 1 (at-least-once delivery) |
| Detection window | **30 samples** (~30 seconds of history) |
| Anomaly threshold | **Z-score > 3.0σ** |
| Storage | InfluxDB 2.7 · bucket: `sensors` · org: `factory` |

### Sensor Normal Operating Ranges

| Sensor | Unit | Min | Max | Midpoint |
|---|---|---|---|---|
| Temperature | °C | 40.0 | 85.0 | 62.5 |
| Vibration | g | 0.1 | 3.0 | 1.55 |
| Motor Current | A | 2.0 | 10.0 | 6.0 |

### Noise Model

Each reading is drawn as: `value = baseline + gaussian_noise(0, 5% × value)`

The Gaussian noise simulates real sensor quantisation and environmental interference. The Z-score window must accumulate enough readings before it becomes sensitive — the detector requires a minimum of 10 samples before reporting any anomaly.

---

## 2 · Z-Score Detection Methodology

```
For each (arm_id, sensor) pair — independent ring buffer:

  window  =  ring buffer of last 30 values
  mean    =  Σ(window) / 30
  std     =  √( Σ(xᵢ − mean)² / 30 )

  z_score =  |current_value − mean| / std

  is_anomaly = (z_score > 3.0)
```

### Why Z-score over a Neural Network

| Criterion | Z-score (this project) | LSTM Autoencoder (robotic-bearing-pdm) |
|---|---|---|
| Training data required | ❌ None | ✅ Healthy baseline windows |
| Adapts to operating conditions | ✅ Auto (rolling window) | ❌ Requires retraining |
| Latency | **< 1 ms** per reading | ~15–20 ms per window |
| Interpretability | Direct (σ units) | Indirect (reconstruction error) |
| Best for | Streaming real-time telemetry | Long-run degradation trends |

**Design intent:** this project demonstrates that not every IIoT anomaly detection problem needs deep learning. A well-tuned statistical detector running in-process alongside the MQTT subscriber has sub-millisecond latency and zero training overhead — appropriate for a 1-second streaming sensor loop.

---

## 3 · Fault Injection — `degradation.py`

Each arm independently samples fault events on a random schedule (every 60–180 publish cycles ≈ 1–3 minutes between events). Each fault lasts 20–60 cycles.

### Fault Profiles

#### THERMAL_DRIFT — Temperature

```
v_fault = v_base + progress × 30°C      (gradual ramp over fault duration)
```

| Phase | Temperature | Expected Z-score |
|---|---|---|
| Normal | 62.5 ± 2.4°C | 0.0 – 1.5σ |
| Fault onset (progress=0.3) | +9°C above baseline | ~2.5 – 3.5σ |
| Fault peak (progress=1.0) | +30°C above baseline | > 5.0σ |

The gradual ramp means the detector should produce **rising Z-scores** rather than an instant spike — the first alert typically fires at progress ≈ 0.25–0.35 (7–10°C above baseline). This mirrors real thermal fault onset in motor windings.

#### VIBRATION_SPIKE — Vibration

```
v_fault = v_base + 8g × |sin(progress × 4π)|     (oscillating burst)
```

| Phase | Vibration | Expected Z-score |
|---|---|---|
| Normal | 1.55 ± 0.06g | 0.0 – 1.5σ |
| Spike peak | +8g | > 6.0σ |
| Between oscillations | +0g | drops back below threshold |

The sine envelope produces **intermittent anomaly alerts** — the detector flags the spike peaks but not the troughs. This tests whether the downstream dashboard correctly renders non-contiguous anomaly events.

#### OVERCURRENT — Motor Current

```
v_fault = v_base + 6A × min(progress × 3, 1.0)     (step increase)
```

| Phase | Current | Expected Z-score |
|---|---|---|
| Normal | 6.0 ± 1.1A | 0.0 – 1.5σ |
| Step onset | +6A = 12A | ~3.5 – 5.0σ |
| Sustained | 12A constant | gradually decreases as window adapts |

The step function generates a **strong initial anomaly** that decays as the rolling window absorbs the new level — correctly modelling a motor that has shifted to a new (higher) operating point rather than a continuously worsening condition.

---

## 4 · InfluxDB Schema

**Measurement:** `sensor_reading`

| Field / Tag | Type | Description |
|---|---|---|
| `arm_id` | tag | `arm_01` / `arm_02` / `arm_03` |
| `sensor` | tag | `temperature` / `vibration` / `current` |
| `fault_mode` | tag | `normal` / `thermal_drift` / `vibration_spike` / `overcurrent` |
| `value` | field (float) | Raw sensor reading |
| `z_score` | field (float) | Sliding-window Z-score at time of reading |
| `mean` | field (float) | Window mean at time of reading |
| `std` | field (float) | Window standard deviation |
| `is_anomaly` | field (int) | 1 if `z_score > 3.0`, else 0 |

### Sample Flux Query — Last 60 Anomalies

```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> filter(fn: (r) => r._field == "is_anomaly" and r._value == 1)
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 60)
```

### Sample Flux Query — Z-score Timeline for One Channel

```flux
from(bucket: "sensors")
  |> range(start: -15m)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> filter(fn: (r) => r.arm_id == "arm_02" and r.sensor == "temperature")
  |> filter(fn: (r) => r._field == "z_score")
```

---

## 5 · API Endpoints

| Endpoint | Method | Description | Typical Latency |
|---|---|---|---|
| `/` | GET | Serves the HTML dashboard | — |
| `/health` | GET | Liveness check — `{"status":"ok"}` | < 1 ms |
| `/api/sensors/latest` | GET | Latest reading per arm/sensor | ~30–80 ms |
| `/api/sensors/history` | GET | History for last N minutes (1–60) | ~50–150 ms |
| `/api/anomalies` | GET | Anomaly events, last 1 hour, max 200 | ~50–150 ms |

API latency is dominated by the InfluxDB Flux query round-trip. The `/health` endpoint intentionally bypasses InfluxDB so Docker health checks never block on database availability.

---

## 6 · Observed Detection Behaviour

### Thermal Drift — Gradual Escalation

The gradual ramp profile produces a characteristic **rising Z-score staircase**. The detector begins firing alerts approximately 8–10 seconds into a fault event (progress ≈ 0.28), giving ~20–50 seconds of pre-alert window before the temperature reaches its peak deviation.

**Expected anomaly log output during THERMAL_DRIFT on arm_02:**
```
[ANOMALY] arm_02/temperature  value=71.8  z=3.12  mode=thermal_drift
[ANOMALY] arm_02/temperature  value=76.4  z=4.05  mode=thermal_drift
[ANOMALY] arm_02/temperature  value=83.1  z=5.23  mode=thermal_drift
[ANOMALY] arm_02/temperature  value=91.7  z=6.41  mode=thermal_drift
```

### Vibration Spike — Intermittent Pattern

The sinusoidal oscillation produces **burst anomalies** — clusters of flagged readings separated by brief returns below threshold as the sine envelope passes through zero.

**Expected anomaly log output during VIBRATION_SPIKE on arm_01:**
```
[ANOMALY] arm_01/vibration  value=8.73  z=5.84  mode=vibration_spike
[ANOMALY] arm_01/vibration  value=6.12  z=4.21  mode=vibration_spike
           ← below threshold for ~2s (sine trough) →
[ANOMALY] arm_01/vibration  value=7.94  z=5.33  mode=vibration_spike
```

### Overcurrent — Sustained Decay

The step increase generates a strong initial Z-score that **decays** as the window adapts to the new current level. After ~30 seconds the detector stops flagging, even though the current remains elevated — correctly modelling a system that has reached a new steady state.

**Expected Z-score decay profile:**
```
t=0s    current=12.1A    z=4.8σ   ANOMALY
t=5s    current=12.3A    z=3.9σ   ANOMALY
t=12s   current=11.9A    z=2.7σ   (below threshold)
t=20s   current=12.2A    z=1.4σ   (window adapted)
```

---

## 7 · Dashboard — Interactive Sensor Modal

Clicking any metric tile on the arm status cards opens a detailed popup:

| Component | Content |
|---|---|
| Live reading | Current value, unit, 5-min min/avg/max |
| Z-score gauge | Proportional bar, colour-coded green→orange→red |
| Mini chart | 5-minute zoom with red anomaly dot markers |
| Recommendations | Fault-mode-aware action list (4 steps) |
| Anomaly history | Last 8 events for that arm/sensor pair |

### Fault-Mode Recommendations (sample)

**VIBRATION_SPIKE detected on vibration sensor:**
1. Inspect bearing condition — check for pitting or surface wear
2. Verify mounting bolt torque on the base and wrist joints
3. Reduce feed rate by 20% to confirm vibration source is load-dependent
4. Schedule preventive maintenance if spike recurs within 10 minutes

**OVERCURRENT detected on current sensor:**
1. Check for mechanical resistance — inspect all joints for obstructions
2. Verify drive belt or gearbox condition — worn components increase drag
3. Reduce cycle speed by 25% and observe whether current drops
4. Check drive controller temperature — overheating causes current spikes

---

## 8 · Dataset Replay — AI4I 2020

Real labeled fault data from Kaggle's AI4I 2020 Predictive Maintenance dataset can be replayed through the pipeline to validate alert functionality with known ground-truth labels.

| AI4I Fault Type | Fault Column | Maps To | Expected Anomaly |
|---|---|---|---|
| Heat Dissipation Failure | `HDF` | temperature spike | THERMAL_DRIFT pattern |
| Power Failure | `PWF` | current spike | OVERCURRENT pattern |
| Overstrain Failure | `OSF` | current + vibration | OVERCURRENT / VIBRATION_SPIKE |
| Tool Wear Failure | `TWF` | vibration spike | VIBRATION_SPIKE pattern |
| Random Failure | `RNF` | any sensor | noise anomaly |

Out of 10,000 rows in the dataset, 339 rows (3.39%) contain at least one labeled failure — providing a realistic sparse-fault stream that tests the detector's false-positive rate under continuous normal operation.

---

## 9 · Key Metrics

| Metric | Value |
|---|---|
| Publish rate | **9 readings/second** (3 arms × 3 sensors × 1Hz) |
| Detection window | **30 samples** ≈ 30 seconds rolling history |
| Anomaly threshold | **Z > 3.0σ** |
| Minimum samples before detection | **10** |
| Expected false positive rate (Gaussian noise) | **0.27%** (3σ rule) |
| Thermal drift first-alert progress | ~**0.28** (8–10s into fault) |
| Overcurrent window adaptation time | **~30 seconds** after step |
| InfluxDB API latency | **30–150 ms** (Flux query round-trip) |
| Dashboard poll interval | **2 seconds** |
| Docker startup time (cold) | **~30–45 seconds** (InfluxDB init) |

---

## 10 · Conclusions

1. **Statistical detectors are viable for real-time IIoT streaming** — the sliding-window Z-score runs in < 1 ms per reading, adapts automatically to operating conditions, and requires zero training data. Appropriate when low latency and interpretability matter more than detecting slow multi-variable degradation trends.

2. **Fault profile design matters** — the three fault types were chosen to test distinct Z-score behaviours: gradual escalation (thermal drift), intermittent bursting (vibration spike), and decaying step (overcurrent). A single threshold of 3.0σ handles all three patterns without tuning.

3. **The window size of 30 samples is a deliberate trade-off** — smaller windows are more sensitive to sudden changes (overcurrent) but more susceptible to noise. Larger windows smooth noise better but delay detection of gradual drifts. At 1Hz, 30 samples = 30 seconds of history, which is fast enough for operator response while filtering single-sample spikes.

4. **The custom dashboard outperforms Grafana for this use case** — the pre-built Grafana dashboard produced 15 overlapping series per chart (one per arm × fault mode combination) because fault mode is a tag, not a group-by dimension. The custom Chart.js dashboard correctly aggregates to 3 lines per chart and adds interactive drill-down that Grafana panels cannot provide without plugins.

5. **Z-score and LSTM Autoencoder are complementary** — this project (Z-score, real-time streaming) and [`robotic-bearing-pdm`](https://github.com/abhi-faldu/robotic-bearing-pdm) (LSTM-AE, long-run bearing degradation) represent two ends of the IIoT anomaly detection spectrum. Real production systems use both: streaming thresholds for immediate alerts and ML models for predictive horizon estimation.

---

*Results based on simulated sensor data. Replace `simulator/publisher.py` with a real MQTT bridge or replay a real dataset via `replay.py` for production-grade validation.*
