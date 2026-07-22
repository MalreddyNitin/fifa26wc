from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
)

spark = SparkSession.builder.appName("live-football-features").getOrCreate()
schema = StructType(
    [
        StructField("schema_version", StringType()),
        StructField("message_id", StringType()),
        StructField("event_id", IntegerType()),
        StructField("observed_at", StringType()),
        StructField("payload", StringType()),
    ]
)
raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "validated-match-updates")
    .option("startingOffsets", "earliest")
    .load()
)
updates = (
    raw.select(F.from_json(F.col("value").cast("string"), schema).alias("m"))
    .select("m.*")
    .withColumn("observed_at", F.to_timestamp("observed_at"))
    .withWatermark("observed_at", "2 minutes")
    .dropDuplicates(["message_id", "observed_at"])
)
features = updates.select(
    "message_id",
    "event_id",
    "observed_at",
    F.get_json_object("payload", "$.event.status.description").alias("status"),
    F.get_json_object("payload", "$.event.homeScore.current")
    .cast("int")
    .alias("home_score"),
    F.get_json_object("payload", "$.event.awayScore.current")
    .cast("int")
    .alias("away_score"),
)
query = (
    features.selectExpr(
        "CAST(event_id AS STRING) AS key",
        "to_json(struct(*)) AS value",
    )
    .writeStream.format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("topic", "live-features")
    .option("checkpointLocation", "/workspace/streaming/checkpoints/live_features")
    .outputMode("append")
    .start()
)
query.awaitTermination()
