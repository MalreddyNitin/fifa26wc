import pandas as pd

from sofascore_api import fetch_json


def empty_match_stats(event_id):
    return pd.DataFrame({
        "side": ["home", "away"],
        "event_id": [event_id, event_id],
    })


def per_match_datawrang(event_id):
    data = fetch_json(
        f"event/{event_id}/statistics",
        cache_group="statistics",
        cache_key=event_id,
        required_key="statistics",
    )
    statistics = data.get("statistics") if data else None

    if not statistics:
        print(f"No statistics available for event {event_id}; using empty rows")
        return empty_match_stats(event_id)

    rows = []

    for period in statistics:
        period_name = period.get("period")

        for group in period.get("groups", []):
            group_name = group.get("groupName")

            for item in group.get("statisticsItems", []):
                rows.append({
                    "period": period_name,
                    "group": group_name,
                    "stat": item.get("name"),
                    "home": item.get("home"),
                    "away": item.get("away"),
                })

    if not rows:
        print(f"No statistics rows available for event {event_id}; using empty rows")
        return empty_match_stats(event_id)

    df = pd.DataFrame(rows)
    df = df[~((df["group"] == "Match overview") & (df["stat"] == "Total shots"))]
    df2 = df.copy()
    df2["stat_col"] = df2["period"] + "_" + df2["stat"]

    wide = (
        df2.melt(
            id_vars=["stat_col"],
            value_vars=["home", "away"],
            var_name="side",
            value_name="value"
        )
        .pivot_table(
            index="side",
            columns="stat_col",
            values="value",
            aggfunc="first"
        )
        .reset_index()
    )

    wide_clean = split_fraction_pct_cols(wide)
    wide_clean = convert_percent_cols(wide_clean)

    for col in wide_clean.columns:
        if col != "side":
            converted = pd.to_numeric(wide_clean[col], errors="coerce")
            if converted.notna().sum() == wide_clean[col].notna().sum():
                wide_clean[col] = converted
    wide_clean = wide_clean.assign(event_id=event_id)
    return wide_clean


def split_fraction_pct_cols(wide):
    wide = wide.copy()

    pattern = r"^(\d+)/(\d+)\s*\((\d+)%\)$"
    split_columns = {}
    columns_to_drop = []

    for col in wide.columns:
        if col == "side":
            continue

        s = wide[col].astype(str).str.strip()

        mask = s.str.match(pattern, na=False)

        if mask.any():
            extracted = s.str.extract(pattern)

            split_columns[f"{col}_won"] = pd.to_numeric(
                extracted[0], errors="coerce"
            )
            split_columns[f"{col}_total"] = pd.to_numeric(
                extracted[1], errors="coerce"
            )
            split_columns[f"{col}_pct"] = (
                pd.to_numeric(extracted[2], errors="coerce") / 100
            )
            columns_to_drop.append(col)

    if split_columns:
        split_df = pd.DataFrame(split_columns, index=wide.index)
        wide = pd.concat(
            [wide.drop(columns=columns_to_drop), split_df],
            axis=1,
        )

    return wide.copy()

#wide_clean = split_fraction_pct_cols(wide)

def convert_percent_cols(wide):
    wide = wide.copy()

    for col in wide.columns:
        if col == "side":
            continue

        s = wide[col].astype(str)

        mask = s.str.match(r"^\s*\d+(\.\d+)?%\s*$", na=False)

        if mask.any():
            converted = (
                pd.to_numeric(
                    s.str.replace("%", "", regex=False),
                    errors="coerce",
                )
                / 100
            )
            wide[col] = wide[col].where(~mask, converted)

    return wide

#wide_clean = convert_percent_cols(wide_clean)
