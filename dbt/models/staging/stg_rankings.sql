select
  event_id,
  home_team_id,
  away_team_id,
  home_displayed_ranking,
  away_displayed_ranking
from {{ ref('stg_events') }}
