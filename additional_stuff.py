from sofascore_api import fetch_json


def safe_get(d, path, default=None):
    """
    Safely get nested dict values.
    Example: safe_get(event, ["venue", "city", "name"])
    """
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur

def get_event_details(event_id):
    data = fetch_json(
        f"event/{event_id}",
        cache_group="event_details",
        cache_key=event_id,
        required_key="event",
    )

    if not data:
        return {"event_id": event_id}

    event = data.get("event", data)

    home_country = safe_get(event, ["homeTeam", "country", "name"])
    away_country = safe_get(event, ["awayTeam", "country", "name"])
    venue_country = safe_get(event, ["venue", "country", "name"])

    # neutral site logic
    if venue_country is None:
        neutral_site = None
    elif venue_country == home_country or venue_country == away_country:
        neutral_site = 0
    else:
        neutral_site = 1

    return {
        "event_id": event_id,

        # rankings
        # "home_fifa_ranking": safe_get(event, ["homeTeam", "ranking"]),
        # "away_fifa_ranking": safe_get(event, ["awayTeam", "ranking"]),

        # teams
        "home_team": safe_get(event, ["homeTeam", "name"]),
        "away_team": safe_get(event, ["awayTeam", "name"]),
        "home_team_id": safe_get(event, ["homeTeam", "id"]),
        "away_team_id": safe_get(event, ["awayTeam", "id"]),
        "home_country": home_country,
        "away_country": away_country,

        # actual match venue
        "venue_name": safe_get(event, ["venue", "name"]),
        "venue_city": safe_get(event, ["venue", "city", "name"]),
        "venue_country": venue_country,
        "venue_latitude": safe_get(event, ["venue", "venueCoordinates", "latitude"]),
        "venue_longitude": safe_get(event, ["venue", "venueCoordinates", "longitude"]),
        "venue_capacity": safe_get(event, ["venue", "capacity"]),

        # neutral flag
        "neutral_site": neutral_site,

        # competition info
        "tournament": safe_get(event, ["tournament", "name"]),
        "unique_tournament": safe_get(event, ["tournament", "uniqueTournament", "name"]),
        "season": safe_get(event, ["season", "name"]),
        "round": safe_get(event, ["roundInfo", "round"]),
        "round_name": safe_get(event, ["roundInfo", "name"]),

        # timestamp / URL stuff
        "start_timestamp": event.get("startTimestamp"),
        "slug": event.get("slug"),
        "custom_id": event.get("customId"),
    }
