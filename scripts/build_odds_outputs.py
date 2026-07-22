from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
input_path = ROOT / "data/samples/odds_import_template.csv"
output = ROOT / "data/predictions"
output.mkdir(parents=True, exist_ok=True)

frame = pd.read_csv(input_path)
frame.to_parquet(ROOT / "data/canonical/fct_odds_snapshots.parquet", index=False)
pd.DataFrame(
    columns=[
        "event_id",
        "bookmaker",
        "market",
        "selection",
        "model_probability",
        "decimal_odds",
        "no_vig_probability",
        "edge",
        "expected_value",
    ]
).to_parquet(output / "pred_expected_value.parquet", index=False)

for filename, title in (
    ("ev_backtest.md", "Expected-value backtest"),
    ("closing_line_value.md", "Closing-line value"),
):
    (ROOT / "reports" / filename).write_text(
        f"# {title}\n\n"
        "No timestamped bookmaker snapshots were supplied, so the platform "
        "does not report fabricated ROI or closing-line results. Import real "
        "pre-kickoff prices with `data/samples/odds_import_template.csv` and "
        "the tested odds utilities will populate this report.\n",
        encoding="utf-8",
    )

print("Odds contracts materialized; 0 real snapshots supplied")
