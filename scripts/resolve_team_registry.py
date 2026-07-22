import argparse
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.client import SofaScoreClient  # noqa: E402


def choose_team(results, search_name):
    candidates = []
    for result in results:
        entity = result.get("entity", {})
        sport = entity.get("sport", {})
        if (
            result.get("type") == "team"
            and sport.get("slug") == "football"
            and entity.get("national") is True
            and entity.get("gender") in {None, "M"}
        ):
            candidates.append(entity)

    if not candidates:
        raise ValueError(f"No men's national football result for {search_name}")

    normalized = search_name.casefold().replace("&", "and")
    exact = [
        entity
        for entity in candidates
        if entity.get("name", "").casefold().replace("&", "and") == normalized
    ]
    return (exact or candidates)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "teams.yml",
    )
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    client = SofaScoreClient(
        raw_root=ROOT / "data" / "raw",
        pipeline_run_id=f"registry-{uuid.uuid4()}",
        request_interval=0.25,
        legacy_cache_root=ROOT / ".sofascore_cache",
    )

    unresolved = []
    for team in config["teams"]:
        if team.get("sofascore_team_id"):
            continue
        result = client.search_team(team["sofascore_search_name"])
        if result is None:
            unresolved.append(team["team_id"])
            continue
        entity = choose_team(
            result.payload.get("results", []),
            team["sofascore_search_name"],
        )
        team["sofascore_team_id"] = int(entity["id"])
        team["sofascore_slug"] = entity["slug"]
        print(
            f"{team['team_id']}: {team['sofascore_team_id']} / {team['sofascore_slug']}"
        )

    if unresolved:
        raise RuntimeError(f"Unresolved teams: {unresolved}")

    args.config.write_text(
        yaml.safe_dump(
            config,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
