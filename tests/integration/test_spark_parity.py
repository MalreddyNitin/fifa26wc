import pandas as pd
import pytest


def test_spark_team_match_grain_if_output_exists(project_root=None):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spark_path = root / "data/lake/silver/fct_team_matches_spark"
    if not spark_path.exists():
        pytest.skip("Spark output is optional in unit-test mode")
    pandas_frame = pd.read_parquet(root / "data/canonical/fct_team_matches.parquet")
    spark_frame = pd.read_parquet(spark_path)
    assert len(spark_frame) == len(pandas_frame)
    assert not spark_frame.duplicated(["event_id", "side"]).any()
