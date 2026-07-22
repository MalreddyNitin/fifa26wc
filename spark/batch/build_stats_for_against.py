from pathlib import Path

from pyspark.sql import SparkSession

ROOT = Path("/workspace")
spark = SparkSession.builder.appName("build-stats-for-against").getOrCreate()
stats = spark.read.parquet(str(ROOT / "data/canonical/fct_team_match_stats.parquet"))
opponent = stats.select(
    "event_id",
    stats.team_id.alias("opponent_id"),
    *[
        stats[column].alias(f"against_{column}")
        for column in stats.columns
        if column.startswith("ALL_")
    ],
)
result = stats.join(opponent, ["event_id", "opponent_id"], "left")
result.write.mode("overwrite").parquet(
    str(ROOT / "data/lake/silver/fct_stats_for_against_spark")
)
spark.stop()
