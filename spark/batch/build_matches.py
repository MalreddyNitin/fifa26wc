from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

ROOT = Path("/workspace")
spark = SparkSession.builder.appName("build-matches").getOrCreate()
source = spark.read.parquet(str(ROOT / "data/canonical/all_world_cup_matches.parquet"))
result = (
    source.dropDuplicates(["event_id"])
    .withColumn("kickoff_utc", F.to_timestamp("kickoff_timestamp"))
    .withColumn(
        "training_eligible",
        (F.col("status_type") == "finished")
        & F.col("home_score").isNotNull()
        & F.col("away_score").isNotNull(),
    )
)
result.write.mode("overwrite").parquet(str(ROOT / "data/lake/silver/fct_matches_spark"))
spark.stop()
