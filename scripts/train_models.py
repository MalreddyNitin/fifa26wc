import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.models.train import train_all_models  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(train_all_models(ROOT), indent=2))
