import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.inference import PredictionService  # noqa: E402
from world_cup_intelligence.prematch import PrematchLookupError  # noqa: E402

API_BASE_URL = os.getenv("API_BASE_URL")
ARTIFACT_ROOT = Path(
    os.getenv(
        "WCI_ARTIFACT_ROOT",
        ROOT
        if (ROOT / "data/canonical/dim_teams.parquet").exists()
        else ROOT / "deployment",
    )
)
DATA_ROOT = ARTIFACT_ROOT / "data"
st.set_page_config(
    page_title="World Cup Intelligence",
    page_icon="⚽",
    layout="wide",
)


@st.cache_data
def load_data():
    teams = pd.read_parquet(DATA_ROOT / "canonical/dim_teams.parquet")
    matches = pd.read_parquet(DATA_ROOT / "canonical/fct_matches.parquet")
    form = pd.read_parquet(DATA_ROOT / "features/team_match_feature_master.parquet")
    tournament_path = DATA_ROOT / "predictions/tournament_probabilities.parquet"
    tournament = (
        pd.read_parquet(tournament_path) if tournament_path.exists() else pd.DataFrame()
    )
    return teams, matches, form, tournament


@st.cache_resource
def prediction_service():
    return PredictionService(ROOT, artifact_root=ARTIFACT_ROOT)


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
            if API_BASE_URL:
                response = requests.post(
                    f"{API_BASE_URL}/v1/predict-sofascore-link",
                    json={"sofascore_url": sofascore_url.strip()},
                    timeout=30,
                )
                response.raise_for_status()
                prediction = response.json()
            else:
                prediction = prediction_service().predict_sofascore_link(
                    sofascore_url.strip()
                )
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
        except (
            requests.RequestException,
            PrematchLookupError,
            FileNotFoundError,
            KeyError,
        ) as exc:
            st.error(f"Prediction service unavailable: {exc}")

with scorelines:
    path = DATA_ROOT / "predictions/pred_scoreline_samples.parquet"
    if path.exists():
        st.dataframe(pd.read_parquet(path).tail(100), use_container_width=True)
    else:
        st.info("Train the scoreline model to populate this view.")

with markets:
    path = DATA_ROOT / "canonical/fct_odds_snapshots.parquet"
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
    coverage_path = DATA_ROOT / "features/feature_coverage_report.csv"
    if coverage_path.exists():
        feature_coverage = pd.read_csv(coverage_path)
        st.metric("Historical matches", f"{len(matches):,}")
        st.metric("Feature columns", f"{len(feature_coverage):,}")
        st.dataframe(feature_coverage, use_container_width=True)

with health:
    manifest = ARTIFACT_ROOT / "manifest.json"
    run_log = DATA_ROOT / "run_logs/pipeline_run_log.json"
    if manifest.exists():
        st.caption(
            "This public app uses a versioned, compact inference snapshot; "
            "the full data lake is not shipped with the web process."
        )
        st.json(manifest.read_text(encoding="utf-8"))
    elif run_log.exists():
        st.json(run_log.read_text(encoding="utf-8"))
    else:
        st.warning("No pipeline run log is available.")
