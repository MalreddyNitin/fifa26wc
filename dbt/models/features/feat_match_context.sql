select
  event_id,
  kickoff_utc,
  home_team_id,
  away_team_id,
  neutral_site,
  competition_type,
  round_name,
  home_displayed_ranking - away_displayed_ranking as ranking_difference
from {{ ref('fct_matches') }}
