import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.simulation.world_cup import (  # noqa: E402
    materialize_simulation,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulations", type=int, default=50_000)
    args = parser.parse_args()
    fixtures, runs, probabilities = materialize_simulation(
        ROOT, simulations=args.simulations
    )
    print(
        f"fixtures={len(fixtures)}, simulations={len(runs):,}, "
        f"teams={len(probabilities)}"
    )
