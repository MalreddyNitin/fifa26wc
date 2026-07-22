select
  event_id, venue_id, venue_name, venue_city, venue_country,
  venue_latitude, venue_longitude, venue_capacity
from {{ ref('stg_events') }}
