from pathlib import Path

import pandas as pd
import yaml

REQUIRED_TEAM_FIELDS = {
    "team_id",
    "team_name",
    "fifa_code",
    "confederation",
    "world_cup_group",
    "host_country_flag",
    "sofascore_search_name",
}


def load_team_registry(path):
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    teams = data.get("teams", [])
    if len(teams) != 48:
        raise ValueError(f"Expected 48 World Cup teams, found {len(teams)}")

    for team in teams:
        missing = REQUIRED_TEAM_FIELDS.difference(team)
        if missing:
            raise ValueError(
                f"Registry entry {team.get('team_id')} is missing {sorted(missing)}"
            )

    frame = pd.DataFrame(teams)
    if frame["team_id"].duplicated().any():
        raise ValueError("team_id must be unique")
    if frame["fifa_code"].duplicated().any():
        raise ValueError("fifa_code must be unique")

    frame["is_world_cup_2026_team"] = True
    frame["country_name"] = frame["team_name"]
    frame["active_from"] = pd.NaT
    frame["active_to"] = pd.NaT
    return frame


def build_aliases(registry):
    aliases = {
        "USA": "united_states",
        "United States": "united_states",
        "United States of America": "united_states",
        "South Korea": "south_korea",
        "Korea Republic": "south_korea",
        "Iran": "iran",
        "IR Iran": "iran",
        "Turkey": "turkey",
        "Türkiye": "turkey",
        "Ivory Coast": "ivory_coast",
        "Côte d'Ivoire": "ivory_coast",
        "DR Congo": "dr_congo",
        "Congo DR": "dr_congo",
        "Cape Verde": "cabo_verde",
        "Cabo Verde": "cabo_verde",
        "Curacao": "curacao",
        "Curaçao": "curacao",
        "Czech Republic": "czechia",
        "Czechia": "czechia",
        "Bosnia & Herzegovina": "bosnia_herzegovina",
        "Bosnia and Herzegovina": "bosnia_herzegovina",
    }
    for row in registry.itertuples(index=False):
        aliases[row.team_name] = row.team_id
        aliases[row.sofascore_search_name] = row.team_id

    return pd.DataFrame(
        [
            {
                "source_name": name,
                "canonical_team_id": team_id,
                "source": "registry",
            }
            for name, team_id in sorted(aliases.items())
        ]
    )
