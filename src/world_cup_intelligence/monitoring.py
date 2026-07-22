from pathlib import Path

import numpy as np
import pandas as pd


def population_stability_index(reference, current, bins=10):
    reference = pd.to_numeric(reference, errors="coerce").dropna()
    current = pd.to_numeric(current, errors="coerce").dropna()
    if reference.empty or current.empty:
        return np.nan
    boundaries = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 3:
        return 0.0
    boundaries[0], boundaries[-1] = -np.inf, np.inf
    ref_counts = np.histogram(reference, bins=boundaries)[0]
    cur_counts = np.histogram(current, bins=boundaries)[0]
    ref_share = np.clip(ref_counts / ref_counts.sum(), 1e-6, None)
    cur_share = np.clip(cur_counts / cur_counts.sum(), 1e-6, None)
    return float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))


def build_drift_report(frame, cutoff=None):
    ordered = frame.sort_values("kickoff_utc")
    cutoff = cutoff or ordered["kickoff_utc"].quantile(0.8)
    reference = ordered.loc[ordered["kickoff_utc"].lt(cutoff)]
    current = ordered.loc[ordered["kickoff_utc"].ge(cutoff)]
    numeric = [
        column
        for column in ordered
        if column.startswith(("rolling_", "opponent_rolling_", "ewm_", "trend_"))
        and ordered[column].notna().sum() >= 100
    ]
    return pd.DataFrame(
        {
            "feature": numeric,
            "reference_mean": [reference[c].mean() for c in numeric],
            "current_mean": [current[c].mean() for c in numeric],
            "psi": [
                population_stability_index(reference[c], current[c]) for c in numeric
            ],
        }
    ).sort_values("psi", ascending=False)


def materialize_monitoring(root):
    root = Path(root)
    master = pd.read_parquet(root / "data/features/team_match_feature_master.parquet")
    report = build_drift_report(master)
    output = root / "reports"
    output.mkdir(parents=True, exist_ok=True)
    report.to_csv(output / "feature_drift_report.csv", index=False)
    run_logs = list((root / "data/run_logs").glob("pipeline_run_*.json"))
    summary = [
        "# Monitoring report",
        "",
        f"- Historical feature rows: {len(master):,}",
        f"- Numeric features monitored: {len(report):,}",
        f"- Pipeline run logs retained: {len(run_logs):,}",
        "- PSI above 0.25 is flagged for review, not automatically treated "
        "as proof of model failure.",
    ]
    (output / "monitoring_report.md").write_text("\n".join(summary), encoding="utf-8")
    return report
