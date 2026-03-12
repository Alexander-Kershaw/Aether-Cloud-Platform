from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, to_date


def main() -> None:
    s3_endpoint = os.environ["S3_ENDPOINT"]
    s3_access_key = os.environ["AWS_ACCESS_KEY_ID"]
    s3_secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]

    spark = (
        SparkSession.builder
        .appName("acp-bronze-to-silver")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", s3_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", s3_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    bronze_path = "s3a://aether-lakehouse/bronze/acp/sample_events/"
    silver_path = "s3a://aether-lakehouse/silver/acp/sample_events/"

    bronze_df = spark.read.parquet(bronze_path)

    silver_df = (
        bronze_df
        .select(
            col("event_id").cast("bigint").alias("event_id"),
            to_date(col("dt")).alias("event_date"),
            current_timestamp().alias("ingest_ts"),
        )
    )

    row_count = silver_df.count()
    print(f"=====| SILVER_ROW_COUNT={row_count} |=====")

    (
        silver_df
        .write
        .mode("overwrite")
        .partitionBy("event_date")
        .parquet(silver_path)
    )

    print(f"=====| WROTE_SILVER_TO={silver_path} |=====")

    spark.stop()


if __name__ == "__main__":
    main()