# Canonical data dictionary

## `fct_matches`

One row per SofaScore `event_id`. Contains UTC kickoff, source team IDs,
platform team IDs, regulation/final scores, tournament/season/round, venue,
neutral-site context, source-displayed rankings, and `training_eligible`.

## `fct_team_matches`

Exactly two rows per match (`home`, `away`). `team_id` and `opponent_id`,
goals for/against, result, points, goal difference, rankings, confederations,
and home/away flags are expressed from that row's team perspective. Fixtures
without final scores retain null targets.

## `fct_team_match_stats`

Two rows only when the endpoint has statistics. Columns are prefixed by period:
`ALL_`, `1ST_`, `2ND_`, `ET_`, `ET1_`, or `ET2_`. Standalone percentages are
decimals. Fraction-and-percentage values use `_won`, `_total`, and `_pct`.
Unsupported endpoints are recorded in coverage tables and never zero-filled.

`home_displayed_ranking` and `away_displayed_ranking` are the rankings exposed
by the source event payload; they are not represented as official historical
FIFA rankings.
