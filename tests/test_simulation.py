import pandas as pd

from world_cup_intelligence.simulation.world_cup import (
    _assign_third_place,
    _rank_group,
    create_group_fixtures,
)


def test_group_fixtures_have_six_matches_per_group():
    registry = pd.DataFrame(
        {
            "team_id": [f"t{i}" for i in range(8)],
            "world_cup_group": ["A"] * 4 + ["B"] * 4,
        }
    )
    result = create_group_fixtures(registry)
    assert result.groupby("group").size().eq(6).all()


def test_group_ranking_is_deterministic():
    teams = ["a", "b", "c", "d"]
    matches = [
        ("a", "b", 1, 0),
        ("a", "c", 0, 0),
        ("a", "d", 0, 0),
        ("b", "c", 0, 0),
        ("b", "d", 0, 0),
        ("c", "d", 0, 0),
    ]
    first, _ = _rank_group(teams, matches)
    second, _ = _rank_group(teams, matches)
    assert first == second


def test_third_place_assignment_uses_each_team_once():
    groups = {group: f"team_{group}" for group in "ABCDEFGH"}
    assignment = _assign_third_place(groups)
    assert len(assignment) == 8
    assert len(set(assignment.values())) == 8
