import get_team_links
import additional_stuff
import per_match_datawrang
import pandas as pd


matches_df = get_team_links.get_team_links(4713, "england")

details_rows = []

for event_id in matches_df["event_id"].dropna().unique():
    print("loading details", event_id)
    details_rows.append(additional_stuff.get_event_details(event_id))

details_df = pd.DataFrame(details_rows)

matches_enriched = matches_df.merge(
    details_df,
    on="event_id",
    how="left",
    suffixes=("", "_details")
)

matches_enriched = matches_enriched.drop(
    columns=[
        "home_team_details",
        "away_team_details",
        "home_country",
        "away_country",
        "venue_latitude",
        "venue_longitude",
        "start_timestamp",
        "slug",
        "custom_id",
    ],
    errors="ignore",
)

match_stats_frames = []

for event_id in matches_enriched["event_id"].dropna().unique():
    print("loading statistics", event_id)
    match_stats = per_match_datawrang.per_match_datawrang(event_id)
    match_stats_frames.append(match_stats)

# concat uses the union of all columns. Stats that are unavailable for a
# particular match are filled with NaN.
if match_stats_frames:
    all_match_stats = pd.concat(
        match_stats_frames,
        ignore_index=True,
        sort=False
    )
else:
    all_match_stats = pd.DataFrame(columns=["side", "event_id"])

matches_enriched = matches_enriched.merge(
    all_match_stats,
    on="event_id",
    how="left",
    validate="one_to_many"
)

matches_enriched.to_csv("matches_enriched.csv", index=False)