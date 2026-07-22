from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

ROOT = Path("/workspace")
spark = SparkSession.builder.appName("build-team-matches").getOrCreate()
matches = spark.read.parquet(str(ROOT / "data/canonical/fct_matches.parquet"))
common = ["event_id", "kickoff_utc", "status_type", "training_eligible"]
home = matches.select(
    *common,
    F.lit("home").alias("side"),
    F.col("home_team_id").alias("team_id"),
    F.col("away_team_id").alias("opponent_id"),
    F.col("home_score_regulation").alias("goals_for"),
    F.col("away_score_regulation").alias("goals_against"),
)
away = matches.select(
    *common,
    F.lit("away").alias("side"),
    F.col("away_team_id").alias("team_id"),
    F.col("home_team_id").alias("opponent_id"),
    F.col("away_score_regulation").alias("goals_for"),
    F.col("home_score_regulation").alias("goals_against"),
)
result = home.unionByName(away)
result.write.mode("overwrite").parquet(
    str(ROOT / "data/lake/silver/fct_team_matches_spark")
)
spark.stop()
