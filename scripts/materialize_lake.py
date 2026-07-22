from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAKE = ROOT / "data" / "lake"


def main():
    mappings = {
        "silver": ROOT / "data" / "canonical",
        "gold": ROOT / "data" / "features",
    }
    for layer, source in mappings.items():
        target = LAKE / layer
        target.mkdir(parents=True, exist_ok=True)
        for path in source.glob("*.parquet"):
            frame = pd.read_parquet(path)
            output = target / path.stem / "part-00000.parquet"
            output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(output, index=False)
    print(f"Lake materialized at {LAKE}")


if __name__ == "__main__":
    main()
