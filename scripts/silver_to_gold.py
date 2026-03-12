from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, count


def main() -> None:
    s3_endpoint = os.environ["S3_ENDPOINT"]
    s3_access_key = os.environ["AWS_ACCESS_KEY_ID"]
    s3_secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]

    spark = (
        SparkSession.builder
        .appName("acp-silver-to-gold")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", s3_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", s3_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    silver_path = "s3a://aether-lakehouse/silver/acp/sample_events/"
    gold_path = "s3a://aether-lakehouse/gold/acp/daily_event_counts/"

    silver_df = spark.read.parquet(silver_path)

    gold_df = (
        silver_df.
        groupBy(col("event_date"))
        .agg(count("*").alias("event_count"))
        .withColumn("load_ts", current_timestamp())
        .select("event_date", "event_count", "load_ts")
    )


    row_count = gold_df.count()
    print(f"=====| GOLD_ROW_COUNT={row_count} |=====")

    (
        gold_df
        .write
        .mode("overwrite")
        .parquet(gold_path)
    )


    print(f"=====| WROTE_GOLD_TO={gold_path} |=====")

    spark.stop()



if __name__ == "__main__":
    main()