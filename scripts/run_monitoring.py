import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.monitoring import materialize_monitoring  # noqa: E402

if __name__ == "__main__":
    report = materialize_monitoring(ROOT)
    print(f"Monitored {len(report):,} features")
