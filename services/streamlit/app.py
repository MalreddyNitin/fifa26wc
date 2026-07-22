import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(
    page_title="World Cup Intelligence",
    page_icon="⚽",
    layout="wide",
)


@st.cache_data
def load_data():
    teams = pd.read_parquet(ROOT / "data/canonical/dim_teams.parquet")
    matches = pd.read_parquet(ROOT / "data/canonical/fct_matches.parquet")
    form = pd.read_parquet(ROOT / "data/features/team_match_feature_master.parquet")
    tournament_path = ROOT / "data/predictions/tournament_probabilities.parquet"
    tournament = (
        pd.read_parquet(tournament_path) if tournament_path.exists() else pd.DataFrame()
    )
    return teams, matches, form, tournament


st.title("World Cup Intelligence")
st.caption(
    "Historical facts, pre-match model outputs, and tournament simulations "
    "are labeled separately throughout."
)
teams, matches, form, tournament = load_data()

overview, explorer, predictor, scorelines, markets, performance, coverage, health = (
    st.tabs(
        [
            "Tournament",
            "Teams",
            "Match predictor",
            "Scorelines",
            "Markets & EV",
            "Model performance",
            "Data coverage",
            "Pipeline health",
        ]
    )
)

with overview:
    st.subheader("Tournament simulation")
    if tournament.empty:
        st.info("Run scripts/simulate_tournament.py to create probabilities.")
    else:
        display = tournament.sort_values("probability_champion", ascending=False)
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.plotly_chart(
            px.bar(
                display.head(20),
                x="team_name",
                y="probability_champion",
                color="world_cup_group",
            ),
            use_container_width=True,
        )

with explorer:
    selected = st.selectbox(
        "Team",
        teams["team_id"].tolist(),
        format_func=lambda value: teams.set_index("team_id").loc[value, "team_name"],
    )
    history = form.loc[form["team_id"].eq(selected)].sort_values("kickoff_utc").tail(20)
    st.dataframe(
        history[
            [
                c
                for c in (
                    "kickoff_utc",
                    "opponent",
                    "goals_for",
                    "goals_against",
                    "result",
                    "elo_pre",
                    "elo_post",
                )
                if c in history
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

with predictor:
    st.caption(
        "Paste the public SofaScore match page. The service fetches event metadata "
        "only; live match statistics are not used as pre-match predictors."
    )
    sofascore_url = st.text_input(
        "SofaScore match link",
        placeholder=("https://www.sofascore.com/football/match/...#id:12345678"),
    )
    if st.button("Fetch match and predict", type="primary"):
        if not sofascore_url.strip():
            st.warning("Enter a SofaScore match link.")
            st.stop()
        try:
            response = requests.post(
                f"{API_BASE_URL}/v1/predict-sofascore-link",
                json={"sofascore_url": sofascore_url.strip()},
                timeout=30,
            )
            response.raise_for_status()
            prediction = response.json()
            cols = st.columns(3)
            cols[0].metric("Home win", f"{prediction['home_win']:.1%}")
            cols[1].metric("Draw", f"{prediction['draw']:.1%}")
            cols[2].metric("Away win", f"{prediction['away_win']:.1%}")
            context = prediction.get("prematch_context", {})
            st.subheader(
                f"{prediction['home_team_id']} vs {prediction['away_team_id']}"
            )
            st.write(
                {
                    "kickoff": context.get("kickoff_utc"),
                    "competition": context.get("tournament_name"),
                    "round": context.get("round_name"),
                    "stadium": context.get("venue_name"),
                    "city": context.get("venue_city"),
                    "country": context.get("venue_country"),
                    "neutral_site": context.get("neutral_site"),
                }
            )
            st.json(prediction)
        except requests.RequestException as exc:
            st.error(f"Prediction service unavailable: {exc}")

with scorelines:
    path = ROOT / "data/predictions/pred_scoreline_samples.parquet"
    if path.exists():
        st.dataframe(pd.read_parquet(path).tail(100), use_container_width=True)
    else:
        st.info("Train the scoreline model to populate this view.")

with markets:
    path = ROOT / "data/canonical/fct_odds_snapshots.parquet"
    if path.exists():
        st.dataframe(pd.read_parquet(path), use_container_width=True)
    else:
        st.info(
            "No bookmaker data has been supplied. Use "
            "data/samples/odds_import_template.csv; no synthetic market prices "
            "are presented as real odds."
        )

with performance:
    report = ROOT / "reports/outcome_baseline_report.md"
    st.markdown(
        report.read_text(encoding="utf-8")
        if report.exists()
        else ("Run `scripts/train_models.py` to generate the model report.")
    )

with coverage:
    coverage_path = ROOT / "data/features/feature_coverage_report.csv"
    if coverage_path.exists():
        feature_coverage = pd.read_csv(coverage_path)
        st.metric("Historical matches", f"{len(matches):,}")
        st.metric("Feature columns", f"{len(feature_coverage):,}")
        st.dataframe(feature_coverage, use_container_width=True)

with health:
    run_log = ROOT / "data/run_logs/pipeline_run_log.json"
    if run_log.exists():
        st.json(run_log.read_text(encoding="utf-8"))
    else:
        st.warning("No pipeline run log is available.")
