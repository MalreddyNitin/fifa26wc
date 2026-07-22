select matches.*
from {{ ref('fct_matches') }} as matches
left join {{ ref('source_event_exceptions') }} as exceptions
  on matches.event_id = exceptions.event_id
 and exceptions.exception_type = 'finished_missing_score'
where matches.status_type = 'finished'
  and (matches.home_score is null or matches.away_score is null)
  and exceptions.event_id is null
