select distinct
  venue_id, venue_name, venue_city, venue_country,
  venue_latitude, venue_longitude, venue_capacity
from {{ ref('stg_event_details') }}
where venue_id is not null
