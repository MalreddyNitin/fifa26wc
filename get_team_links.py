from datetime import datetime, timedelta, timezone

import pandas as pd

from sofascore_api import fetch_json


def sofascore_ts_to_date(ts):
    # SofaScore usually uses seconds, but this protects against milliseconds too
    if abs(ts) > 10_000_000_000:
        ts = ts / 1000

    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts)).date()


def get_team_matches(team_id, team_slug, since_date="11-07-1966"):
    # team_slug remains part of the public function signature because callers
    # already provide it, although this API endpoint only needs the numeric ID.
    _ = team_slug
    since_dt = datetime.strptime(since_date, "%d-%m-%Y").date()

    rows = []

    for page in range(500):
        data = fetch_json(f"team/{team_id}/events/last/{page}")

        if not data:
            print("Stopped at page", page)
            break

        events = data.get("events", [])

        if not events:
            break

        page_dates = []

        for e in events:
            ts = e.get("startTimestamp")
            if ts is None:
            continue

            match_date = sofascore_ts_to_date(ts)
            page_dates.append(match_date)

            if match_date < since_dt:
                continue

            event_id = e.get("id")
            slug = e.get("slug")
            custom_id = e.get("customId")

            if slug and custom_id:
                match_link = f"https://www.sofascore.com/football/match/{slug}/{custom_id}#id:{event_id}"
            else:
                match_link = f"https://www.sofascore.com/event/{event_id}"

            rows.append({
                "event_id": event_id,
                "date": match_date.strftime("%d-%m-%Y"),
                "home_team": e.get("homeTeam", {}).get("name"),
                "away_team": e.get("awayTeam", {}).get("name"),
                "home_score": e.get("homeScore", {}).get("current"),
                "away_score": e.get("awayScore", {}).get("current"),
                "tournament": e.get("tournament", {}).get("name"),
                "season": e.get("season", {}).get("name"),
                "round": e.get("roundInfo", {}).get("round"),
                "link": match_link,
            })

        print("page", page, "events:", len(events))

        # Pages are newest-to-oldest. Once this page crosses the cutoff,
        # later pages cannot contain a match that we need.
        if page_dates and min(page_dates) < since_dt:
            break

    matches_df = pd.DataFrame(rows).drop_duplicates(subset=["event_id"])
    matches_df["date"] = pd.to_datetime(
        matches_df["date"],
        format="%d-%m-%Y",
        errors="coerce",
    )
    matches_df = matches_df.sort_values("date")

    return matches_df


def get_team_links(team_id, team_slug, since_date="11-07-1966"):
    """Backward-compatible wrapper for the original England pipeline."""
    return get_team_matches(team_id, team_slug, since_date)
