select
  own.*,
  opponent."ALL_Total shots" as against_total_shots,
  opponent."ALL_Shots on target" as against_shots_on_target,
  opponent."ALL_Corner kicks" as against_corner_kicks
from {{ ref('stg_team_match_stats') }} own
left join {{ ref('stg_team_match_stats') }} opponent
  on own.event_id = opponent.event_id
 and own.opponent_id = opponent.team_id
