import itertools
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

THIRD_SLOTS = {
    74: set("ABCDF"),
    77: set("CDFGH"),
    79: set("CEFHI"),
    80: set("EHIJK"),
    81: set("BEFIJ"),
    82: set("AEHIJ"),
    85: set("EFGIJ"),
    87: set("DEIJL"),
}
R32_FIXED = {
    73: ("2A", "2B"),
    75: ("1F", "2C"),
    76: ("1C", "2F"),
    78: ("2E", "2I"),
    83: ("2K", "2L"),
    84: ("1H", "2J"),
    86: ("1J", "2H"),
    88: ("2D", "2G"),
}
KNOCKOUT = {
    89: (74, 77),
    90: (73, 75),
    91: (76, 78),
    92: (79, 80),
    93: (83, 84),
    94: (81, 82),
    95: (86, 88),
    96: (85, 87),
    97: (89, 90),
    98: (93, 94),
    99: (91, 92),
    100: (95, 96),
    101: (97, 98),
    102: (99, 100),
    104: (101, 102),
}


def create_group_fixtures(registry):
    rows = []
    match_id = 1
    for group, teams in registry.groupby("world_cup_group", sort=True):
        team_ids = sorted(teams["team_id"])
        for home, away in itertools.combinations(team_ids, 2):
            rows.append(
                {
                    "fixture_id": f"G{match_id:03d}",
                    "stage": "group",
                    "group": group,
                    "home_team_id": home,
                    "away_team_id": away,
                }
            )
            match_id += 1
    return pd.DataFrame(rows)


def _goal_rates(home_elo, away_elo):
    difference = np.clip((home_elo - away_elo) / 400, -1.5, 1.5)
    return (
        float(np.clip(1.30 * np.exp(0.45 * difference), 0.25, 4.5)),
        float(np.clip(1.10 * np.exp(-0.45 * difference), 0.25, 4.5)),
    )


def _play_match(
    home,
    away,
    ratings,
    rng,
    knockout=False,
    parameters=None,
):
    if parameters is None:
        home_rate, away_rate = _goal_rates(ratings[home], ratings[away])
        penalty_home = 1 / (1 + 10 ** ((ratings[away] - ratings[home]) / 800))
    else:
        home_rate, away_rate, penalty_home = parameters[(home, away)]
    home_goals = int(rng.poisson(home_rate))
    away_goals = int(rng.poisson(away_rate))
    if not knockout or home_goals != away_goals:
        winner = home if home_goals > away_goals else away
        return home_goals, away_goals, winner
    # Extra time is one third of regulation expectation. A remaining tie is
    # resolved with a strength-adjusted penalty probability.
    home_goals += int(rng.poisson(home_rate / 3))
    away_goals += int(rng.poisson(away_rate / 3))
    if home_goals != away_goals:
        return (
            home_goals,
            away_goals,
            home if home_goals > away_goals else away,
        )
    winner = home if rng.random() < penalty_home else away
    return home_goals, away_goals, winner


def _rank_group(group_teams, matches):
    table = {team: {"points": 0, "gd": 0, "gf": 0, "wins": 0} for team in group_teams}
    for home, away, home_goals, away_goals in matches:
        table[home]["gf"] += home_goals
        table[away]["gf"] += away_goals
        table[home]["gd"] += home_goals - away_goals
        table[away]["gd"] += away_goals - home_goals
        if home_goals > away_goals:
            table[home]["points"] += 3
            table[home]["wins"] += 1
        elif away_goals > home_goals:
            table[away]["points"] += 3
            table[away]["wins"] += 1
        else:
            table[home]["points"] += 1
            table[away]["points"] += 1

    # FIFA's primary group criteria are points, goal difference, and goals
    # scored. Stable team ID is a deterministic final fallback because the
    # model does not simulate cards/fair-play points.
    ordered = sorted(
        group_teams,
        key=lambda team: (
            -table[team]["points"],
            -table[team]["gd"],
            -table[team]["gf"],
            team,
        ),
    )
    return ordered, table


def _assign_third_place(third_groups):
    """Find a deterministic compatible assignment to FIFA's eight slots."""
    groups = set(third_groups)
    slots = sorted(THIRD_SLOTS, key=lambda slot: len(THIRD_SLOTS[slot] & groups))

    def search(position, remaining, assignment):
        if position == len(slots):
            return assignment
        slot = slots[position]
        for group in sorted(THIRD_SLOTS[slot] & remaining):
            found = search(
                position + 1,
                remaining - {group},
                {**assignment, slot: third_groups[group]},
            )
            if found:
                return found
        return None

    assignment = search(0, groups, {})
    if assignment is None:
        raise ValueError("No compatible third-place bracket assignment")
    return assignment


def simulate_once(
    fixtures,
    registry,
    ratings,
    rng,
    group_specs=None,
    parameters=None,
):
    if group_specs is None:
        group_specs = {
            group: (
                registry.loc[registry["world_cup_group"].eq(group), "team_id"].tolist(),
                [
                    (row.home_team_id, row.away_team_id)
                    for row in group_fixtures.itertuples(index=False)
                ],
            )
            for group, group_fixtures in fixtures.groupby("group", sort=True)
        }
    group_positions = {}
    third_table = []
    for group, (teams, pairings) in group_specs.items():
        results = []
        for home, away in pairings:
            home_goals, away_goals, _ = _play_match(
                home,
                away,
                ratings,
                rng,
                parameters=parameters,
            )
            results.append(
                (
                    home,
                    away,
                    home_goals,
                    away_goals,
                )
            )
        ordered, table = _rank_group(teams, results)
        group_positions[f"1{group}"] = ordered[0]
        group_positions[f"2{group}"] = ordered[1]
        third = ordered[2]
        third_table.append(
            (
                group,
                third,
                table[third]["points"],
                table[third]["gd"],
                table[third]["gf"],
            )
        )
    best_thirds = sorted(
        third_table,
        key=lambda row: (-row[2], -row[3], -row[4], row[1]),
    )[:8]
    third_by_group = {row[0]: row[1] for row in best_thirds}
    third_slots = _assign_third_place(third_by_group)

    winners = {}
    reached = defaultdict(set)
    for team in registry["team_id"]:
        reached["group"].add(team)
    for team in [
        *group_positions.values(),
        *third_by_group.values(),
    ]:
        reached["round_of_32"].add(team)

    for match_id in range(73, 89):
        if match_id in R32_FIXED:
            home_ref, away_ref = R32_FIXED[match_id]
            home, away = group_positions[home_ref], group_positions[away_ref]
        else:
            winner_group = {
                74: "1E",
                77: "1I",
                79: "1A",
                80: "1L",
                81: "1D",
                82: "1G",
                85: "1B",
                87: "1K",
            }[match_id]
            home, away = group_positions[winner_group], third_slots[match_id]
        _, _, winners[match_id] = _play_match(
            home,
            away,
            ratings,
            rng,
            knockout=True,
            parameters=parameters,
        )

    stage_by_match = {
        **{match: "round_of_16" for match in range(89, 97)},
        **{match: "quarterfinal" for match in range(97, 101)},
        **{match: "semifinal" for match in range(101, 103)},
        104: "final",
    }
    for match_id, (left, right) in KNOCKOUT.items():
        home, away = winners[left], winners[right]
        reached[stage_by_match[match_id]].update((home, away))
        _, _, winners[match_id] = _play_match(
            home,
            away,
            ratings,
            rng,
            knockout=True,
            parameters=parameters,
        )
    champion = winners[104]
    reached["champion"].add(champion)
    return champion, reached


def run_simulations(registry, elo_history, simulations=50_000, seed=42):
    fixtures = create_group_fixtures(registry)
    latest = (
        elo_history.sort_values(["kickoff_utc", "event_id"])
        .drop_duplicates("team_id", keep="last")
        .set_index("team_id")["elo_post"]
    )
    ratings = {team: float(latest.get(team, 1500.0)) for team in registry["team_id"]}
    team_ids = registry["team_id"].tolist()
    parameters = {
        (home, away): (
            *_goal_rates(ratings[home], ratings[away]),
            1 / (1 + 10 ** ((ratings[away] - ratings[home]) / 800)),
        )
        for home in team_ids
        for away in team_ids
        if home != away
    }
    group_specs = {
        group: (
            registry.loc[registry["world_cup_group"].eq(group), "team_id"].tolist(),
            [
                (row.home_team_id, row.away_team_id)
                for row in group_fixtures.itertuples(index=False)
            ],
        )
        for group, group_fixtures in fixtures.groupby("group", sort=True)
    }
    rng = np.random.default_rng(seed)
    counts = {
        stage: defaultdict(int)
        for stage in (
            "round_of_32",
            "round_of_16",
            "quarterfinal",
            "semifinal",
            "final",
            "champion",
        )
    }
    simulation_rows = []
    for simulation_id in range(simulations):
        champion, reached = simulate_once(
            fixtures,
            registry,
            ratings,
            rng,
            group_specs=group_specs,
            parameters=parameters,
        )
        simulation_rows.append(
            {"simulation_id": simulation_id, "champion_team_id": champion}
        )
        for stage in counts:
            for team in reached[stage]:
                counts[stage][team] += 1
    probabilities = registry[["team_id", "team_name", "world_cup_group"]].copy()
    for stage, values in counts.items():
        probabilities[f"probability_{stage}"] = probabilities["team_id"].map(
            lambda team: values[team] / simulations
        )
    return fixtures, pd.DataFrame(simulation_rows), probabilities


def materialize_simulation(root, simulations=50_000):
    root = Path(root)
    registry = pd.read_parquet(root / "data/canonical/dim_teams.parquet")
    elo = pd.read_parquet(root / "data/features/team_elo_history.parquet")
    fixtures, runs, probabilities = run_simulations(
        registry, elo, simulations=simulations
    )
    output = root / "data" / "predictions"
    output.mkdir(parents=True, exist_ok=True)
    fixtures.to_parquet(
        root / "data" / "canonical" / "world_cup_2026_fixtures.parquet",
        index=False,
    )
    runs.to_parquet(output / "pred_tournament_simulations.parquet", index=False)
    probabilities.to_parquet(output / "tournament_probabilities.parquet", index=False)
    return fixtures, runs, probabilities
