import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.statistics import StatisticsIngestionPipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-events", type=int)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pipeline = StatisticsIngestionPipeline(
        ROOT,
        ROOT / "configs" / "pipelines.yml",
    )
    raw, wide, states = pipeline.run(max_events=args.max_events)
    print(
        f"long rows={len(raw):,}; wide rows={len(wide):,}; "
        f"available={states['status'].eq('available').sum():,}; "
        f"unsupported={states['status'].eq('unsupported').sum():,}; "
        f"failed={states['status'].eq('failed').sum():,}"
    )


if __name__ == "__main__":
    main()
