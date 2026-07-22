select distinct
  unique_tournament_id,
  unique_tournament_name,
  tournament_id,
  tournament_name,
  competition_type
from {{ ref('stg_events') }}
