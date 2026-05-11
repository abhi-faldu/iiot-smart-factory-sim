import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "detector"))
sys.path.insert(0, str(ROOT / "api"))

# Provide required env vars so api/main.py can be imported without a real InfluxDB
os.environ.setdefault("INFLUX_TOKEN", "test-token")
