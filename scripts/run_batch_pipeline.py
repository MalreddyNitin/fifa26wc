import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.pipeline import (  # noqa: E402
    AllTeamIngestionPipeline,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-details", type=int)
    parser.add_argument("--skip-enrichment", action="store_true")
    parser.add_argument("--enrich-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pipeline = AllTeamIngestionPipeline(
        ROOT,
        ROOT / "configs" / "teams.yml",
        ROOT / "configs" / "pipelines.yml",
    )
    if args.enrich_only:
        registry, events, matches = pipeline.run_enrichment_only(
            max_details=args.max_details,
        )
    else:
        registry, events, matches = pipeline.run(
            max_pages=args.max_pages,
            max_details=args.max_details,
            skip_enrichment=args.skip_enrichment,
        )
    print(
        f"Registry: {len(registry)} teams; "
        f"team-event rows: {len(events):,}; "
        f"unique matches: {matches['event_id'].nunique():,}"
    )


if __name__ == "__main__":
    main()
